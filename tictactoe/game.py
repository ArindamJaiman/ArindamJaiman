"""
Tic-Tac-Toe Game Engine for GitHub Profile README
Players take turns by opening GitHub Issues. 
X always goes first. The game alternates between X and O.
"""

import json
import os
import sys
import re

REPO = os.environ.get("REPOSITORY", "ArindamJaiman/ArindamJaiman")
GAME_STATE_FILE = "tictactoe/game_state.json"
README_FILE = "Readme.md"
MOVE_ERROR_FILE = "tictactoe/move_error.txt"

# ── Board rendering using emojis ──────────────────────────────────────────────
CELL_DISPLAY = {
    "X": "❌",
    "O": "⭕",
    " ": "⬜"
}

def load_game_state():
    """Load the current game state from JSON file."""
    default_state = {
        "board": [" "] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "move_count": 0,
        "last_player": None,
        "recent_moves": []
    }
    
    if not os.path.exists(GAME_STATE_FILE):
        return default_state
    
    try:
        with open(GAME_STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default_state


def save_game_state(state):
    """Save the current game state to JSON file."""
    os.makedirs(os.path.dirname(GAME_STATE_FILE), exist_ok=True)
    with open(GAME_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_winner(board):
    """Check if there's a winner. Returns 'X', 'O', 'draw', or None."""
    win_combos = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # cols
        [0, 4, 8], [2, 4, 6]               # diagonals
    ]
    
    for combo in win_combos:
        a, b, c = combo
        if board[a] == board[b] == board[c] and board[a] != " ":
            return board[a]
    
    if " " not in board:
        return "draw"
    
    return None


def make_move(state, position, player_login):
    """Attempt to make a move. Returns (success, message)."""
    if state["game_over"]:
        return False, "Game is already over! Click **New Game** to start fresh."
    
    if position < 0 or position > 8:
        return False, f"Invalid position `{position}`. Must be 0-8."
    
    if state["board"][position] != " ":
        return False, f"Position `{position}` is already taken!"
    
    # Prevent same user from moving twice in a row
    if state["last_player"] == player_login:
        return False, "You just moved! Let someone else take the next turn. 🤝"
    
    # Make the move
    state["board"][position] = state["current_player"]
    state["move_count"] += 1
    
    # Record the move
    move_record = {
        "player": player_login,
        "symbol": state["current_player"],
        "position": position
    }
    state["recent_moves"].insert(0, move_record)
    state["recent_moves"] = state["recent_moves"][:5]  # Keep last 5
    
    # Check for winner
    result = check_winner(state["board"])
    if result:
        state["game_over"] = True
        state["winner"] = result
    
    # Switch player
    state["current_player"] = "O" if state["current_player"] == "X" else "X"
    state["last_player"] = player_login
    
    return True, "Move successful!"


def new_game():
    """Reset the game to a fresh state."""
    state = {
        "board": [" "] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "move_count": 0,
        "last_player": None,
        "recent_moves": []
    }
    return state


def generate_board_markdown(state):
    """Generate the Tic-Tac-Toe board as markdown for the README."""
    board = state["board"]
    current = state["current_player"]
    
    lines = []
    
    lines.append("## 🎮 Community Tic-Tac-Toe")
    lines.append("")
    
    if state["game_over"]:
        if state["winner"] == "draw":
            lines.append("**🤝 It's a draw!** Well played, everyone!")
        else:
            lines.append(f"**🎉 {CELL_DISPLAY[state['winner']]} {state['winner']} wins!** Congratulations! 🏆")
        lines.append("")
        lines.append(f'[![New Game](https://img.shields.io/badge/🎮_New_Game-Play_Again!-brightgreen?style=for-the-badge)](https://github.com/{REPO}/issues/new?title=ttt%7Cnew&body=Just+push+%27Submit+new+issue%27+to+start+a+new+game!)')
    else:
        lines.append(f"**It's {CELL_DISPLAY[current]} {current}'s turn!** Click an empty cell to make your move. Anyone can play! 👋")
    
    lines.append("")
    lines.append("<!-- TICTACTOE_BOARD_START -->")
    lines.append("")
    
    # Build the visual board using a markdown table
    lines.append('<div align="center">')
    lines.append("")
    lines.append("|   | **1** | **2** | **3** |")
    lines.append("|---|-------|-------|-------|")
    
    for row in range(3):
        row_cells = []
        for col in range(3):
            pos = row * 3 + col
            cell = board[pos]
            if cell == " " and not state["game_over"]:
                # Empty cell — make it a clickable link
                link = f"https://github.com/{REPO}/issues/new?title=ttt%7Cmove%7C{pos}&body=Just+push+%27Submit+new+issue%27.+You+don%27t+need+to+do+anything+else."
                row_cells.append(f"[{CELL_DISPLAY[cell]}]({link})")
            else:
                row_cells.append(CELL_DISPLAY[cell])
        
        row_label = chr(65 + row)  # A, B, C
        lines.append(f"| **{row_label}** | {row_cells[0]} | {row_cells[1]} | {row_cells[2]} |")
    
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("<!-- TICTACTOE_BOARD_END -->")
    lines.append("")
    
    # How to play
    lines.append("<details>")
    lines.append("<summary><b>🤔 How does this work?</b></summary>")
    lines.append("<br/>")
    lines.append("")
    lines.append("1. Click on any ⬜ empty cell above")
    lines.append("2. It opens a GitHub Issue — just click **Submit new issue**")
    lines.append("3. A GitHub Action processes your move and updates the board")
    lines.append("4. The board refreshes with your move! Players alternate between ❌ and ⭕")
    lines.append("")
    lines.append("*Built with Python & GitHub Actions — no backend server needed!*")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    
    # Recent moves
    if state["recent_moves"]:
        lines.append("**Last moves:**")
        lines.append("")
        lines.append("| # | Player | Symbol | Position |")
        lines.append("|---|--------|--------|----------|")
        for i, move in enumerate(state["recent_moves"][:5]):
            lines.append(f"| {i+1} | [@{move['player']}](https://github.com/{move['player']}) | {CELL_DISPLAY[move['symbol']]} | {move['position']} |")
        lines.append("")
    
    return "\n".join(lines)


def update_readme(game_markdown):
    """Update the README.md with the new game board."""
    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Normalize line endings to \n for consistent processing
    content = content.replace("\r\n", "\n")
    
    # Look for existing game section markers
    start_marker = "<!-- TICTACTOE_START -->"
    end_marker = "<!-- TICTACTOE_END -->"
    
    if start_marker in content and end_marker in content:
        # Replace existing game section
        pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
        replacement = start_marker + "\n\n" + game_markdown + "\n\n" + end_marker
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        # Game section doesn't exist yet — add before footer
        print("WARNING: Game markers not found in README. Adding before footer.")
        footer_idx = content.find('<div align="center">\n  <img src="https://user-images.githubusercontent.com/74038190/212284100')
        if footer_idx != -1:
            insert_content = start_marker + "\n\n" + game_markdown + "\n\n" + end_marker + "\n\n"
            content = content[:footer_idx] + insert_content + content[footer_idx:]
        else:
            # Last resort: append to end
            content += "\n\n" + start_marker + "\n\n" + game_markdown + "\n\n" + end_marker + "\n"
    
    with open(README_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    """Main entry point — called by GitHub Actions."""
    issue_title = os.environ.get("ISSUE_TITLE", "")
    player_login = os.environ.get("EVENT_USER_LOGIN", "unknown")
    
    if not issue_title.startswith("ttt|"):
        print("Not a tic-tac-toe command. Skipping.")
        sys.exit(0)
    
    parts = issue_title.split("|")
    command = parts[1] if len(parts) > 1 else ""
    
    state = load_game_state()
    
    # Clean up any previous error file
    if os.path.exists(MOVE_ERROR_FILE):
        os.remove(MOVE_ERROR_FILE)
    
    if command == "new":
        state = new_game()
        save_game_state(state)
        print("New game started!")
    elif command == "move":
        if len(parts) < 3:
            print("ERROR: No position specified.")
            sys.exit(1)
        
        try:
            position = int(parts[2])
        except ValueError:
            print(f"ERROR: Invalid position '{parts[2]}'")
            sys.exit(1)
        
        success, message = make_move(state, position, player_login)
        if not success:
            print(f"MOVE FAILED: {message}")
            # Write error to a file in the repo (not /tmp) so later steps can read it
            os.makedirs(os.path.dirname(MOVE_ERROR_FILE), exist_ok=True)
            with open(MOVE_ERROR_FILE, "w") as f:
                f.write(message)
        else:
            save_game_state(state)
            print(f"Move successful: {player_login} played {position}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    # Generate and update README
    game_md = generate_board_markdown(state)
    update_readme(game_md)
    print("README updated successfully!")


if __name__ == "__main__":
    main()
