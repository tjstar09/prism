"""
PRISM - Persistent, Responsive, Interactive Session Manager
A powerful terminal interface for Gemini CLI with remote session sharing, 
automatic persistence, and production-grade security.

Features:
  - Rich TUI with markdown rendering and color-coded output
  - Session recovery: Auto-save/load conversation state as JSON
  - Context window management: Auto-truncate old turns to avoid token limits
  - Full-text search over conversation history
  - Production security: TLS encryption, JWT auth, structured logging
  - Remote proxy: Share terminal sessions across LAN securely
"""

import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import re
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame, TextArea, SearchBufferControl
    Application = Application
except ImportError:
    Application = None

# ============================================================================
# Configuration & Constants
# ============================================================================

TOKEN_PREFIX = b"AUTH "
RESIZE_PREFIX = b"\x00RESIZE "
SEARCH_PREFIX = b"\x00SEARCH "

# Logging configuration
PRISM_HOME = Path.home() / ".prism"
PRISM_HOME.mkdir(exist_ok=True)
LOG_FILE = PRISM_HOME / "prism.log"
SESSION_DIR = PRISM_HOME / "sessions"
SESSION_DIR.mkdir(exist_ok=True)
CONFIG_FILE = PRISM_HOME / "config.json"

# Setup logging
logger = logging.getLogger("PRISM")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5
)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    prompt: str
    response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tokens_used: int = 0


@dataclass
class PrismSession:
    """A complete conversation session with metadata."""
    session_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    turns: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PrismSession":
        return cls(**data)

    def save(self, directory: Path = SESSION_DIR) -> Path:
        """Save session to JSON file."""
        file_path = directory / f"{self.session_id}.json"
        file_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info(f"Session saved: {file_path}")
        return file_path

    @classmethod
    def load(cls, session_id: str, directory: Path = SESSION_DIR) -> Optional["PrismSession"]:
        """Load session from JSON file."""
        file_path = directory / f"{session_id}.json"
        if not file_path.exists():
            logger.warning(f"Session file not found: {file_path}")
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            session = cls.from_dict(data)
            logger.info(f"Session loaded: {file_path}")
            return session
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None


class SearchResult:
    """Result of a search operation."""
    def __init__(self, turn_idx: int, text: str, context: str):
        self.turn_idx = turn_idx
        self.text = text
        self.context = context


# ============================================================================
# Markdown Rendering
# ============================================================================

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


# ============================================================================
# Context Window Management
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Rough estimate of token count (1 token ≈ 4 chars)."""
    return len(text) // 4


def build_context_prompt(
    turns: list[dict[str, str]], 
    next_prompt: str, 
    max_turns: Optional[int] = None,
    max_tokens: int = 100000
) -> str:
    """Build context prompt, auto-truncating old turns to stay within token limits."""
    
    if not turns:
        return next_prompt

    # Calculate tokens for the next prompt
    next_tokens = estimate_tokens(next_prompt)
    available_tokens = max_tokens - next_tokens - 5000  # Reserve 5k for safety

    # If max_turns is set, use that directly
    if max_turns:
        turns_to_include = turns[-max_turns:]
    else:
        # Include as many recent turns as fit within token budget
        turns_to_include = []
        token_count = 0
        for turn in reversed(turns):
            turn_tokens = estimate_tokens(turn["prompt"]) + estimate_tokens(turn["response"])
            if token_count + turn_tokens > available_tokens:
                break
            turns_to_include.insert(0, turn)
            token_count += turn_tokens

    transcript_parts = [
        "Continue this conversation. Use the prior turns as context, then answer the latest user prompt.",
        "",
    ]

    if len(turns_to_include) < len(turns):
        transcript_parts.append(f"[Context truncated: showing {len(turns_to_include)}/{len(turns)} turns]")
        transcript_parts.append("")

    for turn in turns_to_include:
        transcript_parts.append(f"User:\n{turn['prompt'].strip()}")
        transcript_parts.append(f"Assistant:\n{turn['response'].strip()}")
        transcript_parts.append("")

    transcript_parts.append(f"Latest user prompt:\n{next_prompt.strip()}")
    result = "\n".join(transcript_parts)
    
    logger.debug(f"Context built with {len(turns_to_include)}/{len(turns)} turns, ~{estimate_tokens(result)} tokens")
    return result


# ============================================================================
# Search Functionality
# ============================================================================

def search_turns(turns: list[dict[str, str]], query: str, context_lines: int = 2) -> list[SearchResult]:
    """Search across all turns (prompts and responses)."""
    results = []
    query_lower = query.lower()
    
    for idx, turn in enumerate(turns):
        for field in ["prompt", "response"]:
            text = turn[field]
            if query_lower in text.lower():
                # Get context around the match
                lines = text.split("\n")
                for line_idx, line in enumerate(lines):
                    if query_lower in line.lower():
                        start = max(0, line_idx - context_lines)
                        end = min(len(lines), line_idx + context_lines + 1)
                        context = "\n".join(lines[start:end])
                        results.append(SearchResult(idx, line, context))
    
    logger.info(f"Search for '{query}' found {len(results)} results")
    return results


# ============================================================================
# Gemini Integration
# ============================================================================

def get_gemini_executable() -> str:
    """Return the full path to the Gemini CLI executable or raise FileNotFoundError."""
    gemini_executable = shutil.which("gemini")
    if gemini_executable:
        logger.debug(f"Found Gemini executable: {gemini_executable}")
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
        "# PRISM - Gemini Response\n\n"
        f"**Prompt:**\n\n{prompt.strip()}\n\n"
        f"**Response:**\n\n{output.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")
    logger.info(f"Response saved: {path}")
    return path


# ============================================================================
# TUI Application
# ============================================================================

def build_terminal_app(session_id: Optional[str] = None) -> Application:
    """Build the PRISM Terminal User Interface."""
    if Application is None:
        raise RuntimeError("prompt_toolkit is required for TUI mode. Install it with: pip install prompt_toolkit")

    # Load session if provided
    current_session = None
    if session_id:
        current_session = PrismSession.load(session_id)
        if not current_session:
            current_session = PrismSession(session_id=session_id)
    else:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_session = PrismSession(session_id=session_id)

    conversation: list[dict[str, str]] = [
        {"prompt": turn["prompt"], "response": turn["response"]}
        for turn in current_session.turns
    ]

    input_area = TextArea(
        height=10,
        prompt="> ",
        multiline=True,
        wrap_lines=True,
        style="class:input-area",
    )

    transcript_state = {
        "text": "PRISM conversation will appear here.",
        "scroll_line": 0,
        "search_results": [],
        "search_index": 0,
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
        text="F5/Ctrl-S Submit  Ctrl-F Transcript  Ctrl-P Prompt  Ctrl-/ Search  PgUp/PgDn Scroll  Ctrl-R Reset  Ctrl-C Quit"
    )
    status_bar = Window(height=1, content=status_control, style="class:status")

    info_control = FormattedTextControl(
        text=[
            ("class:info", f"Session: {current_session.session_id} | Turns: {len(conversation)}\n"),
            ("class:info", "Enter a prompt in the top editor, then press Ctrl-S to send it to Gemini. Press Ctrl-/ to search."),
        ]
    )
    info_bar = Window(height=2, content=info_control, style="class:info")

    body = HSplit(
        [
            Frame(input_area, title="PRISM Prompt", style="class:frame"),
            Frame(output_window, title="PRISM Chat Transcript", style="class:frame"),
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
            return "PRISM conversation will appear here."

        sections: list[str] = ["# PRISM Chat Transcript", ""]
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
                logger.error(f"Gemini executable not found: {exc}")
            except subprocess.CalledProcessError as exc:
                response_text = (
                    "Gemini CLI failed:\n"
                    f"{exc.stderr or exc.stdout or str(exc)}"
                )
                error_occurred = True
                logger.error(f"Gemini CLI error: {exc}")

            conversation.append({"prompt": prompt_text, "response": response_text})
            set_transcript(render_transcript(), scroll_to_bottom=True)
            app.layout.focus(input_area)

            if not error_occurred:
                try:
                    # Save to markdown
                    save_path = await asyncio.get_running_loop().run_in_executor(
                        None,
                        save_to_markdown,
                        response_text,
                        prompt_text,
                        Path(__file__).resolve().parent,
                    )

                    # Update session and save
                    current_session.turns.append({
                        "prompt": prompt_text,
                        "response": response_text,
                        "timestamp": datetime.now().isoformat(),
                        "tokens_used": estimate_tokens(prompt_text) + estimate_tokens(response_text),
                    })
                    current_session.updated_at = datetime.now().isoformat()
                    await asyncio.get_running_loop().run_in_executor(
                        None, current_session.save
                    )

                    update_status(f"Done. Session saved: {current_session.session_id} | Turns: {len(conversation)}")
                except Exception as save_error:
                    update_status(f"Response received, but saving failed: {save_error}")
                    logger.error(f"Save error: {save_error}")
            else:
                update_status("Finished with errors. See response window for details.")
        finally:
            run_in_progress["active"] = False
            spinner_task.cancel()
            app.invalidate()

    def perform_search() -> None:
        search_query = input_area.text.strip()
        if not search_query:
            update_status("Enter a search term in the prompt box and press Ctrl-/")
            return
        
        results = search_turns(conversation, search_query)
        if not results:
            update_status(f"No results found for '{search_query}'")
            return
        
        transcript_state["search_results"] = results
        transcript_state["search_index"] = 0

        sections = [f"# Search Results for '{search_query}' ({len(results)} matches)", ""]
        for i, result in enumerate(results, 1):
            sections.extend([
                f"## Match {i} (Turn {result.turn_idx + 1})",
                "",
                f"**Context:**",
                "",
                result.context,
                "",
            ])

        set_transcript("\n".join(sections), scroll_to_bottom=True)
        update_status(f"Found {len(results)} matches. Press Ctrl-P to return to input.")

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
        current_session.turns.clear()
        set_transcript(render_transcript(), scroll_to_bottom=False)
        update_status("Chat reset. Type a new prompt and press Ctrl-S.")

    @kb.add("c-r")
    def reset_chat(event) -> None:
        if run_in_progress["active"]:
            return
        conversation.clear()
        current_session.turns.clear()
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

    @kb.add("c-slash")  # Ctrl+/
    def search_transcript(event) -> None:
        app.layout.focus(input_area)
        perform_search()

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

    logger.info(f"TUI app created for session: {current_session.session_id}")
    return app


# ============================================================================
# Terminal Size Handling
# ============================================================================

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


# ============================================================================
# Authentication (JWT-based with fallback to token)
# ============================================================================

def create_auth_token(secret: str, expires_in_hours: int = 24) -> str:
    """Create a JWT token (if available) or simple token."""
    if HAS_JWT:
        payload = {
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
        }
        return jwt.encode(payload, secret, algorithm="HS256")
    else:
        # Fallback to simple token (not recommended for production)
        import hashlib
        return hashlib.sha256(f"{secret}{datetime.now()}".encode()).hexdigest()


def verify_auth_token(token: str, secret: str) -> bool:
    """Verify a JWT token (if available) or simple token."""
    if HAS_JWT and token.startswith("eyJ"):
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
            return True
        except jwt.InvalidTokenError:
            return False
    else:
        # Simple token verification (for backward compatibility)
        return token == secret


async def read_auth(reader: asyncio.StreamReader, token: Optional[str]) -> bool:
    if not token:
        return True
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=10)
    except asyncio.TimeoutError:
        logger.warning("Auth timeout")
        return False
    received_token = line[len(TOKEN_PREFIX):-1].decode("utf-8", errors="ignore") if line.startswith(TOKEN_PREFIX) else ""
    is_valid = verify_auth_token(received_token, token)
    logger.info(f"Auth check: {'passed' if is_valid else 'failed'}")
    return is_valid


async def write_auth(writer: asyncio.StreamWriter, token: Optional[str]) -> None:
    if token:
        auth_token = create_auth_token(token)
        writer.write(TOKEN_PREFIX + auth_token.encode("utf-8") + b"\n")
        await writer.drain()
        logger.debug("Auth token sent to server")


# ============================================================================
# TLS Support
# ============================================================================

def create_ssl_context(cert_file: Optional[str] = None, key_file: Optional[str] = None) -> Optional[ssl.SSLContext]:
    """Create an SSL context for TLS connections."""
    if not cert_file or not key_file:
        return None
    
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_file, key_file)
        logger.info(f"TLS enabled: {cert_file}")
        return context
    except Exception as e:
        logger.error(f"Failed to create SSL context: {e}")
        return None


# ============================================================================
# Remote Proxy: Server
# ============================================================================

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
        logger.warning("Client auth failed")
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
        logger.warning("Client auth failed")
        return

    import pty

    gemini_executable = get_gemini_executable()
    pid, master_fd = pty.fork()

    if pid == 0:
        os.execvp(gemini_executable, [gemini_executable])

    loop = asyncio.get_running_loop()
    peer = writer.get_extra_info("peername")
    logger.info(f"Gemini session started for {peer}")

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
        logger.info(f"Gemini session closed for {peer}")


async def serve(
    host: str,
    port: int,
    token: Optional[str],
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
) -> None:
    """Start the PRISM server."""
    ssl_context = create_ssl_context(cert_file, key_file)

    server = await asyncio.start_server(
        lambda reader, writer: run_pty_server(reader, writer, token),
        host,
        port,
        ssl=ssl_context,
    )
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"🌟 PRISM server listening on {addrs}")
    if token:
        print("🔐 Auth token required for clients.")
    if ssl_context:
        print("🔒 TLS encryption enabled.")
    logger.info(f"PRISM server started on {addrs}")
    async with server:
        await server.serve_forever()


# ============================================================================
# Remote Proxy: Client
# ============================================================================

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


async def connect_client(
    host: str,
    port: int,
    token: Optional[str],
    use_tls: bool = False,
) -> None:
    """Connect to a PRISM server."""
    ssl_context = ssl.create_default_context() if use_tls else None

    reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)
    await write_auth(writer, token)
    writer.write(terminal_size_payload())
    await writer.drain()

    logger.info(f"Connected to PRISM server at {host}:{port}")

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
        logger.info("Disconnected from PRISM server")


# ============================================================================
# CLI & Main
# ============================================================================

def run_tui(session_id: Optional[str] = None) -> None:
    """Run the TUI application."""
    app = build_terminal_app(session_id)
    app.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PRISM - Persistent, Responsive, Interactive Session Manager"
    )
    subparsers = parser.add_subparsers(dest="command")

    # TUI command
    tui_parser = subparsers.add_parser("tui", help="Open the PRISM TUI.")
    tui_parser.add_argument("--session", help="Load a specific session by ID.")
    tui_parser.set_defaults(command="tui")

    # Server command
    server_parser = subparsers.add_parser("server", help="Host a PRISM server.")
    server_parser.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for LAN access.")
    server_parser.add_argument("--port", type=int, default=8765, help="TCP port to listen on.")
    server_parser.add_argument("--token", help="Auth token (required for production). Generates JWT if PyJWT installed.")
    server_parser.add_argument("--cert", help="TLS certificate file (required for production).")
    server_parser.add_argument("--key", help="TLS private key file (required for production).")

    # Client command
    client_parser = subparsers.add_parser("client", help="Connect to a PRISM server.")
    client_parser.add_argument("host", help="Server hostname or IP address.")
    client_parser.add_argument("--port", type=int, default=8765, help="TCP port to connect to.")
    client_parser.add_argument("--token", help="Auth token configured on the server.")
    client_parser.add_argument("--tls", action="store_true", help="Use TLS encryption.")

    # Session management
    session_parser = subparsers.add_parser("sessions", help="List saved sessions.")
    session_parser.set_defaults(command="sessions")

    args = parser.parse_args()
    if args.command is None:
        args.command = "tui"
    return args


def list_sessions() -> None:
    """List all saved sessions."""
    sessions = list(SESSION_DIR.glob("*.json"))
    if not sessions:
        print("No saved sessions found.")
        return

    print("\n🌟 PRISM Saved Sessions:\n")
    for session_file in sorted(sessions, reverse=True):
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            session_id = data["session_id"]
            turns = len(data.get("turns", []))
            created = data["created_at"]
            print(f"  {session_id} | {turns} turns | {created}")
        except Exception as e:
            print(f"  Error reading {session_file.name}: {e}")


def main() -> None:
    args = parse_args()
    
    if args.command == "server":
        asyncio.run(serve(args.host, args.port, args.token, args.cert, args.key))
    elif args.command == "client":
        asyncio.run(connect_client(args.host, args.port, args.token, args.tls))
    elif args.command == "sessions":
        list_sessions()
    else:
        run_tui(args.session)


if __name__ == "__main__":
    main()
