"""
Format agent output for web UI display.
Categorizes different types of outputs and provides structured formatting.
"""

import json
import re
from enum import Enum
from typing import Optional, Dict, Any


class OutputType(Enum):
    """Types of outputs from the agent"""
    STEP_HEADER = "step_header"
    TOOL_CALL = "tool_call"
    CODE_BLOCK = "code_block"
    CODE_EXECUTION = "code_execution"
    PLAN = "plan"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    SEPARATOR = "separator"
    TITLE = "title"
    SECTION = "section"
    MESSAGE = "message"


class OutputFormatter:
    """Formats agent output into structured JSON for web display"""

    def __init__(self):
        self.buffer = ""
        self.outputs = []

    def add_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Add text and try to parse it into structured output.
        Returns structured output dict if a complete message is detected.
        """
        self.buffer += text

        # Try to detect and extract different output types
        output = self._detect_output_type()
        if output:
            return output
        return None

    def _detect_output_type(self) -> Optional[Dict[str, Any]]:
        """Detect output type from buffer and return structured data"""

        # Check for step headers (━━━━ Step 1 ━━━━)
        step_match = re.search(r"(━+.*?Step \d+.*?━+)", self.buffer)
        if step_match:
            step_header = step_match.group(1)
            step_num = re.search(r"Step (\d+)", step_header)
            self.buffer = self.buffer[step_match.end() :]
            return {
                "type": OutputType.STEP_HEADER.value,
                "content": step_header.strip(),
                "step_number": int(step_num.group(1)) if step_num else None,
            }

        # Check for tool calls (Calling tool: 'xxx')
        if "Calling tool:" in self.buffer:
            tool_match = re.search(
                r"Calling tool: '([^']+)' with arguments: (.+?)(?=\n|$)",
                self.buffer,
                re.DOTALL,
            )
            if tool_match:
                tool_name = tool_match.group(1)
                args_str = tool_match.group(2).strip()
                self.buffer = self.buffer[tool_match.end() :]
                try:
                    args = json.loads(args_str)
                except:
                    args = args_str
                return {
                    "type": OutputType.TOOL_CALL.value,
                    "content": f"Calling tool: '{tool_name}'",
                    "tool_name": tool_name,
                    "arguments": args,
                }

        # Check for code execution markers
        if "Executing parsed code:" in self.buffer:
            code_match = re.search(
                r"─ Executing parsed code:.*?─+",
                self.buffer,
                re.DOTALL,
            )
            if code_match:
                code_section = code_match.group(0)
                self.buffer = self.buffer[code_match.end() :]
                return {
                    "type": OutputType.CODE_EXECUTION.value,
                    "content": code_section.strip(),
                }

        # Check for plans
        if "Initial plan" in self.buffer or "Here are the facts I know" in self.buffer:
            # Extract until next major section
            plan_match = re.search(
                r"(Here are the facts.*?)(?=━+|Output message|Calling tool:|$)",
                self.buffer,
                re.DOTALL,
            )
            if plan_match:
                plan_text = plan_match.group(1)
                self.buffer = self.buffer[plan_match.end() :]
                return {
                    "type": OutputType.PLAN.value,
                    "content": plan_text.strip(),
                }

        # Check for final answer
        if "Final Answer:" in self.buffer or "final_answer" in self.buffer:
            answer_match = re.search(
                r"(?:Final Answer|✓ Final Answer):\s*(.+?)(?=\n\n|\Z)",
                self.buffer,
                re.DOTALL,
            )
            if answer_match:
                answer_text = answer_match.group(1).strip()
                self.buffer = self.buffer[answer_match.end() :]
                return {
                    "type": OutputType.FINAL_ANSWER.value,
                    "content": answer_text,
                }

        # Check for observations
        if "Observations:" in self.buffer:
            obs_match = re.search(
                r"Observations:(.+?)(?=\n━|Output message|Calling tool:|$)",
                self.buffer,
                re.DOTALL,
            )
            if obs_match:
                obs_text = obs_match.group(0)
                self.buffer = self.buffer[obs_match.end() :]
                return {
                    "type": OutputType.OBSERVATION.value,
                    "content": obs_text.strip(),
                }

        # Check for errors
        if "Error:" in self.buffer or "✗" in self.buffer:
            error_match = re.search(
                r"(?:✗ )?Error:(.+?)(?=\n|$)",
                self.buffer,
            )
            if error_match:
                error_text = error_match.group(0)
                self.buffer = self.buffer[error_match.end() :]
                return {
                    "type": OutputType.ERROR.value,
                    "content": error_text.strip(),
                }

        # Check for section separators
        if re.match(r"^─+", self.buffer):
            sep_match = re.match(r"─+.*?─+", self.buffer)
            if sep_match:
                separator = sep_match.group(0)
                self.buffer = self.buffer[sep_match.end() :]
                return {
                    "type": OutputType.SEPARATOR.value,
                    "content": separator,
                }

        # If buffer is getting too large and doesn't match patterns, flush it as message
        if len(self.buffer) > 500:
            lines = self.buffer.split("\n")
            # Keep last line in buffer
            content = "\n".join(lines[:-1])
            self.buffer = lines[-1]
            if content.strip():
                return {
                    "type": OutputType.MESSAGE.value,
                    "content": content.strip(),
                }

        return None

    def flush(self) -> Optional[Dict[str, Any]]:
        """Flush any remaining buffer content"""
        if self.buffer.strip():
            content = self.buffer.strip()
            self.buffer = ""
            return {
                "type": OutputType.MESSAGE.value,
                "content": content,
            }
        return None


# Test the formatter
if __name__ == "__main__":
    formatter = OutputFormatter()

    test_input = """Using model: o1
Question: Give me a travel guide
────────────────────────────────── Initial plan ──────────────────────────────────
Here are the facts I know and the plan of action that I will follow:
```
## Plan
1. Search for information
2. Compile guide
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Step 1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Calling tool: 'web_search' with arguments: {'query': 'travel guide'}
Observations:
Found results about travel...
"""

    for chunk in test_input.split("\n"):
        chunk += "\n"
        output = formatter.add_text(chunk)
        if output:
            print(f"TYPE: {output['type']}")
            print(f"CONTENT: {output['content'][:100]}...")
            print("---")

    final = formatter.flush()
    if final:
        print(f"FINAL TYPE: {final['type']}")
        print(f"FINAL CONTENT: {final['content'][:100]}...")
