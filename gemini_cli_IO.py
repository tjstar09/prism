import argparse
import asyncio
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import re
from typing import Optional

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame, TextArea
except ImportError:
    Application = None


TOKEN_PREFIX = b"AUTH "
RESIZE_PREFIX = b"\x00RESIZE "


def render_markdown_fragments(markdown_text: str) -> list[tuple[str, str]]:
    """Render a practical subset of Markdown as prompt_toolkit styled fragments."""
    if not markdown_text:
        return [("class:muted", "Gemini response will appear here.")]

    fragments: list[tuple[str, str]] = []
    in_code_block = False

    def append_inline(text: str, base_style: str = "class:response-text") -> None:
        parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("`") and part.endswith("`") and len(part) > 1:
                fragments.append(("class:inline-code", part))
            elif part.startswith("**") and part.endswith("**") and len(part) > 3:
                fragments.append(("class:bold", part[2:-2]))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                fragments.append(("class:italic", part[1:-1]))
            else:
                fragments.append((base_style, part))

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            in_code_block = not in_code_block
            fragments.append(("class:code-fence", line + "\n"))
            continue

        if in_code_block:
            fragments.append(("class:code-block", raw_line + "\n"))
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        bullet = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
        numbered = re.match(r"^(\s*)(\d+[.)])\s+(.*)$", line)

        if not line:
            fragments.append(("", "\n"))
        elif heading:
            level = len(heading.group(1))
            style = "class:heading" if level <= 2 else "class:subheading"
            fragments.append((style, heading.group(2) + "\n"))
        elif line.startswith(">"):
            fragments.append(("class:quote", line + "\n"))
        elif bullet:
            fragments.append(("class:list-marker", f"{bullet.group(1)}{bullet.group(2)} "))
            append_inline(bullet.group(3))
            fragments.append(("", "\n"))
        elif numbered:
            fragments.append(("class:list-marker", f"{numbered.group(1)}{numbered.group(2)} "))
            append_inline(numbered.group(3))
            fragments.append(("", "\n"))
        else:
            append_inline(line)
            fragments.append(("", "\n"))

    return fragments


class MarkdownResponseLexer(Lexer):
    """Small markdown lexer for prompt_toolkit TextArea output."""

    def lex_document(self, document):
        lines = document.lines

        def in_code_block_before(lineno: int) -> bool:
            in_code = False
            for previous in lines[:lineno]:
                if previous.lstrip().startswith("```"):
                    in_code = not in_code
            return in_code

        def get_line(lineno: int) -> list[tuple[str, str]]:
            if lineno >= len(lines):
                return []

            raw_line = lines[lineno]
            line = raw_line.rstrip()
            in_code = in_code_block_before(lineno)

            if line.startswith("```"):
                return [("class:code-fence", raw_line)]
            if in_code:
                return [("class:code-block", raw_line)]
            if not line:
                return [("", raw_line)]

            heading = re.match(r"^(#{1,6})\s+(.*)$", line)
            bullet = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
            numbered = re.match(r"^(\s*)(\d+[.)])\s+(.*)$", line)

            if heading:
                level = len(heading.group(1))
                style = "class:heading" if level <= 2 else "class:subheading"
                return [(style, heading.group(2))]
            if line.startswith(">"):
                return [("class:quote", raw_line)]
            if bullet:
                return [
                    ("class:list-marker", f"{bullet.group(1)}{bullet.group(2)} "),
                    *self._inline_fragments(bullet.group(3)),
                ]
            if numbered:
                return [
                    ("class:list-marker", f"{numbered.group(1)}{numbered.group(2)} "),
                    *self._inline_fragments(numbered.group(3)),
                ]
            return self._inline_fragments(raw_line)

        return get_line

    @staticmethod
    def _inline_fragments(text: str) -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("`") and part.endswith("`") and len(part) > 1:
                fragments.append(("class:inline-code", part))
            elif part.startswith("**") and part.endswith("**") and len(part) > 3:
                fragments.append(("class:bold", part[2:-2]))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                fragments.append(("class:italic", part[1:-1]))
            else:
                fragments.append(("class:response-text", part))
        return fragments


def build_context_prompt(turns: list[dict[str, str]], next_prompt: str) -> str:
    if not turns:
        return next_prompt

    transcript_parts = [
        "Continue this conversation. Use the prior turns as context, then answer the latest user prompt.",
        "",
    ]
    for turn in turns:
        transcript_parts.append(f"User:\n{turn['prompt'].strip()}")
        transcript_parts.append(f"Assistant:\n{turn['response'].strip()}")
        transcript_parts.append("")
    transcript_parts.append(f"Latest user prompt:\n{next_prompt.strip()}")
    return "\n".join(transcript_parts)


def get_gemini_executable() -> str:
    """Return the full path to the Gemini CLI executable or raise FileNotFoundError."""
    gemini_executable = shutil.which("gemini")
    if gemini_executable:
        return gemini_executable
    raise FileNotFoundError("Gemini CLI not found. Make sure 'gemini' is installed and on PATH.")


def run_gemini(prompt: str) -> str:
    """Run the local Gemini CLI and return the generated response."""
    gemini_executable = get_gemini_executable()
    try:
        result = subprocess.run(
            [gemini_executable, prompt],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        result = subprocess.run(
            [gemini_executable],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
        )
    return result.stdout.strip()


def save_to_markdown(output: str, prompt: str, folder: Path) -> Path:
    """Save the response and prompt to a markdown file in the same folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gemini_response_{timestamp}.md"
    path = folder / filename
    content = (
        "# Gemini Response\n\n"
        f"**Prompt:**\n\n{prompt.strip()}\n\n"
        f"**Response:**\n\n{output.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def build_terminal_app() -> Application:
    if Application is None:
        raise RuntimeError("prompt_toolkit is required for TUI mode. Install it with: pip install prompt_toolkit")

    conversation: list[dict[str, str]] = []

    input_area = TextArea(
        height=10,
        prompt="> ",
        multiline=True,
        wrap_lines=True,
        style="class:input-area",
    )

    transcript_state = {
        "text": "Gemini conversation will appear here.",
        "scroll_line": 0,
    }
    output_control = FormattedTextControl(
        text=lambda: render_markdown_fragments(visible_transcript_text()),
        focusable=True,
        show_cursor=False,
    )
    output_window = Window(
        content=output_control,
        wrap_lines=True,
        style="class:output-area",
    )

    status_control = FormattedTextControl(
        text="F5/Ctrl-S Submit  Ctrl-F Transcript  Ctrl-P Prompt  PgUp/PgDn Scroll  Ctrl-R Reset  Ctrl-C Quit"
    )
    status_bar = Window(height=1, content=status_control, style="class:status")

    info_control = FormattedTextControl(
        text=[
            ("class:info", "Enter a prompt in the top editor, then press Ctrl-S to send it to Gemini.\n"),
            ("class:info", "New prompts continue the chat; older turns stay in the transcript below."),
        ]
    )
    info_bar = Window(height=2, content=info_control, style="class:info")

    body = HSplit(
        [
            Frame(input_area, title="Gemini Prompt", style="class:frame"),
            Frame(output_window, title="Gemini Chat Transcript", style="class:frame"),
            info_bar,
            status_bar,
        ]
    )

    kb = KeyBindings()
    run_in_progress = {"active": False}

    def update_status(text: str) -> None:
        status_control.text = text
        app.invalidate()

    def visible_transcript_text() -> str:
        lines = transcript_state["text"].splitlines()
        if not lines:
            return ""
        scroll_line = max(0, min(transcript_state["scroll_line"], len(lines) - 1))
        transcript_state["scroll_line"] = scroll_line
        visible_lines = lines[scroll_line:]
        if scroll_line > 0:
            visible_lines.insert(0, f"> ... scrolled to line {scroll_line + 1} of {len(lines)}")
            visible_lines.insert(1, "")
        return "\n".join(visible_lines)

    def render_transcript(pending_prompt: Optional[str] = None, pending_note: str = "") -> str:
        if not conversation and not pending_prompt:
            return "Gemini conversation will appear here."

        sections: list[str] = ["# Gemini Chat Transcript", ""]
        for index, turn in enumerate(conversation, start=1):
            sections.extend(
                [
                    f"## Turn {index}",
                    "",
                    "**You**",
                    "",
                    turn["prompt"].strip(),
                    "",
                    "**Gemini**",
                    "",
                    turn["response"].strip(),
                    "",
                ]
            )
        if pending_prompt:
            sections.extend(
                [
                    f"## Turn {len(conversation) + 1}",
                    "",
                    "**You**",
                    "",
                    pending_prompt.strip(),
                    "",
                    "**Gemini**",
                    "",
                    pending_note,
                    "",
                ]
            )
        return "\n".join(sections).rstrip()

    def set_transcript(text: str, *, scroll_to_bottom: bool = True) -> None:
        transcript_state["text"] = text
        line_count = max(1, len(text.splitlines()))
        if scroll_to_bottom:
            transcript_state["scroll_line"] = max(0, line_count - 18)
        else:
            transcript_state["scroll_line"] = 0
        app.invalidate()

    def scroll_transcript(lines: int) -> None:
        line_count = max(1, len(transcript_state["text"].splitlines()))
        transcript_state["scroll_line"] = max(
            0,
            min(line_count - 1, transcript_state["scroll_line"] + lines),
        )
        app.layout.focus(output_window)
        status_control.text = (
            f"Transcript line {transcript_state['scroll_line'] + 1}/{line_count}. "
            "Use Ctrl-P to return to the prompt."
        )
        app.invalidate()

    def submit_current_prompt() -> None:
        if run_in_progress["active"]:
            update_status("Gemini is still responding. Wait for this turn to finish.")
            return
        prompt_text = input_area.text.strip()
        if not prompt_text:
            app.layout.focus(input_area)
            update_status("Please type a prompt before submitting.")
            return
        input_area.text = ""
        input_area.buffer.cursor_position = 0
        set_transcript(
            render_transcript(prompt_text, pending_note="_Waiting for Gemini..._"),
            scroll_to_bottom=True,
        )
        app.layout.focus(input_area)
        app.create_background_task(process_prompt(prompt_text))

    async def spinner() -> None:
        spinner_frames = ["|", "/", "-", "\\"]
        index = 0
        while run_in_progress["active"]:
            status_control.text = f"Running Gemini... {spinner_frames[index % len(spinner_frames)]}"
            app.invalidate()
            index += 1
            await asyncio.sleep(0.1)

    async def process_prompt(prompt_text: str) -> None:
        run_in_progress["active"] = True
        spinner_task = asyncio.create_task(spinner())
        response_text = ""
        error_occurred = False

        try:
            try:
                gemini_prompt = build_context_prompt(conversation, prompt_text)
                response_text = await asyncio.get_running_loop().run_in_executor(
                    None, run_gemini, gemini_prompt
                )
                if not response_text.strip():
                    response_text = "[Gemini returned an empty response]"
            except FileNotFoundError as exc:
                response_text = (
                    f"Error: {exc}\n\n"
                    "Make sure 'gemini' is installed and on PATH. "
                    "Restart your terminal if you just changed your PATH."
                )
                error_occurred = True
            except subprocess.CalledProcessError as exc:
                response_text = (
                    "Gemini CLI failed:\n"
                    f"{exc.stderr or exc.stdout or str(exc)}"
                )
                error_occurred = True

            conversation.append({"prompt": prompt_text, "response": response_text})
            set_transcript(render_transcript(), scroll_to_bottom=True)
            app.layout.focus(input_area)

            if not error_occurred:
                try:
                    save_path = await asyncio.get_running_loop().run_in_executor(
                        None,
                        save_to_markdown,
                        response_text,
                        prompt_text,
                        Path(__file__).resolve().parent,
                    )
                    update_status(f"Done. Saved response to: {save_path}")
                except Exception as save_error:
                    update_status(f"Response received, but saving failed: {save_error}")
            else:
                update_status("Finished with errors. See response window for details.")
        finally:
            run_in_progress["active"] = False
            spinner_task.cancel()
            app.invalidate()

    @kb.add("c-s", eager=True)
    def submit_prompt(event) -> None:
        submit_current_prompt()

    @kb.add("f5", eager=True)
    def submit_prompt_f5(event) -> None:
        submit_current_prompt()

    @kb.add("escape", "enter", eager=True)
    def submit_prompt_escape_enter(event) -> None:
        submit_current_prompt()

    @kb.add("c-n")
    def clear_prompt(event) -> None:
        if run_in_progress["active"]:
            return
        input_area.text = ""
        update_status("Prompt cleared. Type a new prompt and press Ctrl-S.")

    @kb.add("c-l")
    def clear_response(event) -> None:
        if run_in_progress["active"]:
            return
        conversation.clear()
        set_transcript(render_transcript(), scroll_to_bottom=False)
        update_status("Chat reset. Type a new prompt and press Ctrl-S.")

    @kb.add("c-r")
    def reset_chat(event) -> None:
        if run_in_progress["active"]:
            return
        conversation.clear()
        input_area.text = ""
        set_transcript(render_transcript(), scroll_to_bottom=False)
        update_status("Chat reset. Prompt and transcript cleared.")

    @kb.add("c-f")
    def focus_response(event) -> None:
        app.layout.focus(output_window)
        update_status("Transcript focused. Use PgUp/PgDn or Home/End to scroll.")

    @kb.add("c-p")
    def focus_prompt(event) -> None:
        app.layout.focus(input_area)
        update_status("Prompt focused. Type your next prompt and press Ctrl-S.")

    @kb.add("pagedown")
    def scroll_response_down(event) -> None:
        scroll_transcript(12)

    @kb.add("pageup")
    def scroll_response_up(event) -> None:
        scroll_transcript(-12)

    @kb.add("end")
    def scroll_response_bottom(event) -> None:
        line_count = max(1, len(transcript_state["text"].splitlines()))
        transcript_state["scroll_line"] = max(0, line_count - 18)
        app.layout.focus(output_window)
        app.invalidate()

    @kb.add("home")
    def scroll_response_top(event) -> None:
        transcript_state["scroll_line"] = 0
        app.layout.focus(output_window)
        app.invalidate()

    @kb.add("c-c")
    def exit_app(event) -> None:
        event.app.exit()

    style = Style.from_dict(
        {
            "status": "reverse",
            "frame.label": "bold",
            "input-area": "bg:#1e1e1e #ffffff",
            "output-area": "bg:#0b1020 #dbeafe",
            "response-text": "#dbeafe",
            "muted": "#94a3b8 italic",
            "heading": "#facc15 bold",
            "subheading": "#38bdf8 bold",
            "bold": "#f8fafc bold",
            "italic": "#c4b5fd italic",
            "inline-code": "bg:#1f2937 #86efac",
            "code-fence": "#f472b6 bold",
            "code-block": "bg:#111827 #a7f3d0",
            "list-marker": "#fb923c bold",
            "quote": "#93c5fd italic",
            "info": "bg:#111827 #d1d5db",
        }
    )

    app = Application(
        layout=Layout(body, focused_element=input_area),
        key_bindings=kb,
        style=style,
        full_screen=True,
        mouse_support=True,
    )

    return app


def set_terminal_size(fd: int, columns: int, rows: int) -> None:
    if os.name != "posix":
        return
    import fcntl
    import termios

    size = struct.pack("HHHH", rows, columns, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, size)


def terminal_size_payload() -> bytes:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return RESIZE_PREFIX + f"{size.columns} {size.lines}\n".encode("ascii")


def parse_resize_message(data: bytes) -> Optional[tuple[int, int]]:
    if not data.startswith(RESIZE_PREFIX):
        return None
    try:
        columns_text, rows_text = data[len(RESIZE_PREFIX):].strip().split(maxsplit=1)
        return int(columns_text), int(rows_text)
    except ValueError:
        return None


async def read_auth(reader: asyncio.StreamReader, token: Optional[str]) -> bool:
    if not token:
        return True
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=10)
    except asyncio.TimeoutError:
        return False
    return line == TOKEN_PREFIX + token.encode("utf-8") + b"\n"


async def write_auth(writer: asyncio.StreamWriter, token: Optional[str]) -> None:
    if token:
        writer.write(TOKEN_PREFIX + token.encode("utf-8") + b"\n")
        await writer.drain()


async def pipe_reader_to_writer(reader, writer) -> None:
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def run_pipe_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, token: Optional[str]) -> None:
    if not await read_auth(reader, token):
        writer.close()
        await writer.wait_closed()
        return

    gemini_executable = get_gemini_executable()
    process = await asyncio.create_subprocess_exec(
        gemini_executable,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    await asyncio.gather(
        pipe_reader_to_writer(reader, process.stdin),
        pipe_reader_to_writer(process.stdout, writer),
        return_exceptions=True,
    )


async def run_pty_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, token: Optional[str]) -> None:
    if os.name != "posix":
        await run_pipe_server(reader, writer, token)
        return

    if not await read_auth(reader, token):
        writer.close()
        await writer.wait_closed()
        return

    import pty

    gemini_executable = get_gemini_executable()
    pid, master_fd = pty.fork()

    if pid == 0:
        os.execvp(gemini_executable, [gemini_executable])

    loop = asyncio.get_running_loop()
    peer = writer.get_extra_info("peername")
    print(f"Gemini session started for {peer}", file=sys.stderr)

    async def socket_to_pty() -> None:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            resize = parse_resize_message(data)
            if resize:
                set_terminal_size(master_fd, resize[0], resize[1])
                try:
                    os.kill(pid, signal.SIGWINCH)
                except ProcessLookupError:
                    pass
                continue
            await loop.run_in_executor(None, os.write, master_fd, data)

    async def pty_to_socket() -> None:
        while True:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            writer.write(data)
            await writer.drain()

    try:
        await asyncio.gather(socket_to_pty(), pty_to_socket(), return_exceptions=True)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        writer.close()
        await writer.wait_closed()
        print(f"Gemini session closed for {peer}", file=sys.stderr)


async def serve(host: str, port: int, token: Optional[str]) -> None:
    server = await asyncio.start_server(
        lambda reader, writer: run_pty_server(reader, writer, token),
        host,
        port,
    )
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"Gemini terminal server listening on {addrs}")
    if token:
        print("Auth token is required for clients.")
    async with server:
        await server.serve_forever()


async def client_stdin_to_socket(writer: asyncio.StreamWriter) -> None:
    loop = asyncio.get_running_loop()
    while True:
        data = await loop.run_in_executor(None, os.read, sys.stdin.fileno(), 4096)
        if not data:
            break
        writer.write(data)
        await writer.drain()


async def client_socket_to_stdout(reader: asyncio.StreamReader) -> None:
    loop = asyncio.get_running_loop()
    while True:
        data = await reader.read(4096)
        if not data:
            break
        await loop.run_in_executor(None, os.write, sys.stdout.fileno(), data)


async def connect_client(host: str, port: int, token: Optional[str]) -> None:
    reader, writer = await asyncio.open_connection(host, port)
    await write_auth(writer, token)
    writer.write(terminal_size_payload())
    await writer.drain()

    old_attrs = None
    if os.name == "posix" and sys.stdin.isatty():
        import termios
        import tty

        old_attrs = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())

        def send_resize() -> None:
            writer.write(terminal_size_payload())

        signal.signal(signal.SIGWINCH, lambda _signum, _frame: send_resize())

    try:
        await asyncio.gather(
            client_stdin_to_socket(writer),
            client_socket_to_stdout(reader),
            return_exceptions=True,
        )
    finally:
        if old_attrs is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attrs)
        writer.close()
        await writer.wait_closed()


def run_tui() -> None:
    app = build_terminal_app()
    app.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gemini CLI helper: one-shot TUI or full remote terminal proxy."
    )
    subparsers = parser.add_subparsers(dest="command")

    tui_parser = subparsers.add_parser("tui", help="Open the prompt/response TUI.")
    tui_parser.set_defaults(command="tui")

    server_parser = subparsers.add_parser("server", help="Host a Gemini CLI terminal session.")
    server_parser.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for LAN access.")
    server_parser.add_argument("--port", type=int, default=8765, help="TCP port to listen on.")
    server_parser.add_argument("--token", help="Shared token clients must provide.")

    client_parser = subparsers.add_parser("client", help="Connect to a hosted Gemini CLI terminal.")
    client_parser.add_argument("host", help="Server hostname or IP address.")
    client_parser.add_argument("--port", type=int, default=8765, help="TCP port to connect to.")
    client_parser.add_argument("--token", help="Shared token configured on the server.")

    args = parser.parse_args()
    if args.command is None:
        args.command = "tui"
    return args


def main() -> None:
    args = parse_args()
    if args.command == "server":
        asyncio.run(serve(args.host, args.port, args.token))
    elif args.command == "client":
        asyncio.run(connect_client(args.host, args.port, args.token))
    else:
        run_tui()


if __name__ == "__main__":
    main()
