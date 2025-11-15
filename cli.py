
import os
import time
from typing import Optional
from dotenv import load_dotenv
from slack_bolt import App
from textual.app import App as TextualApp, ComposeResult
from textual.widgets import Header, Footer, Input, Static, Label, Button, RichLog
from textual.widgets import Button as TextualButton
from textual.containers import Container, Vertical, ScrollableContainer
from textual.binding import Binding
from textual.message import Message
from textual import work

load_dotenv()


class ChannelLabel(Label):
    def __init__(self, channel_name: str, channel_id: str):
        super().__init__()
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.update(f"#{channel_name} ({channel_id})")
    
    def on_click(self) -> None:
        self.post_message(ChannelSelected(self.channel_id, self.channel_name))


class ChannelSelected(Message):    
    def __init__(self, channel_id: str, channel_name: str):
        super().__init__()
        self.channel_id = channel_id
        self.channel_name = channel_name


class QuitStatic(Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.styles.height = 3
        self.styles.padding = (0, 2, 0, 2)
        self.styles.content_align_vertical = "middle"
        self.styles.content_align_horizontal = "center"
        self.styles.text_align = "center"
        self.styles.align = ("center", "middle")
    
    def on_click(self) -> None:
        self.post_message(QuitRequested())


class CustomFooter(Footer):
    def compose(self) -> ComposeResult:
        yield QuitStatic("Quit", id="quit_btn")


class QuitRequested(Message):
    ...


class BotCLI(TextualApp):
    ENABLE_COMMAND_PALETTE = False
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main_container {
        layout: vertical;
        height: 100%;
        padding: 2;
        align: center middle;
    }
    
    #input_container {
        width: 80;
        margin: 2;
    }
    
    #input_label {
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
    }
    
    #channel_input {
        width: 100%;
        height: 3;
    }
    
    #suggestions_container {
        width: 80;
        max-height: 20;
        border: solid $primary;
        margin-top: 1;
        padding: 1;
        display: none;
    }
    
    #suggestions_container.visible {
        display: block;
    }
    
    #suggestions_list {
        height: 100%;
    }
    
    ChannelLabel {
        padding: 0 1;
        margin: 0;
        border: solid transparent;
        height: auto;
        min-height: 1;
    }
    
    ChannelLabel:hover {
        background: $primary 20%;
        border: solid $primary;
    }
    
    ChannelLabel.--highlight {
        background: $primary;
        border: solid $accent;
    }
    
    #status_text {
        margin-top: 1;
        text-align: center;
        height: 3;
    }
    
    #status_text.loading {
        color: $warning;
    }
    
    #status_text.success {
        color: $success;
    }
    
    #status_text.error {
        color: $error;
    }
    
    CustomFooter {
        align: left middle;
    }
    
    #quit_btn {
        margin-left: 1;
        padding: 0 2;
        height: 3;
        width: 10;
        background: $error;
        color: white;
        text-style: bold;
        border: solid $error;
        content-align: center middle;
        text-align: center;
        align: center middle;
    }
    
    #quit_btn:hover {
        background: $error 80%;
        border: solid $accent;
    }
    
    #message_container {
        width: 80;
        margin: 2;
    }
    
    #channel_header {
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
        color: $success;
    }
    
    #messages_display {
        height: 20;
        border: solid $primary;
        margin-bottom: 1;
        padding: 1;
    }
    
    #message_input {
        width: 100%;
        height: 3;
    }
    
    #back_button {
        margin-top: 2;
        width: 20;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "select_first_suggestion", "Select First"),
        Binding("up", "navigate_up", "Up"),
        Binding("down", "navigate_down", "Down"),
    ]

    def __init__(self):
        super().__init__()
        self.channels: list[dict] = []
        self.filtered_channels: list[dict] = []
        self.slack_app: Optional[App] = None
        self.suggestion_labels: list[ChannelLabel] = []
        self.selected_index: int = 0
        self.selected_channel_id: Optional[str] = None
        self.selected_channel_name: Optional[str] = None
        self.user_cache: dict[str, str] = {}
        self.refresh_messages_task = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="main_container"):
            with Vertical(id="input_container"):
                yield Static(
                    "Enter channel name (type to search, use Tab/Arrow keys to navigate):",
                    id="input_label"
                )
                yield Input(
                    placeholder="#channel-name or type to search...",
                    id="channel_input"
                )
                
                with Container(id="suggestions_container"):
                    with Vertical(id="suggestions_list"):
                        ...
                
                yield Static("", id="status_text")
        
        yield CustomFooter()

    async def on_mount(self) -> None:
        self.title = "Slack Bot CLI"        
        input_widget = self.query_one("#channel_input", Input)
        input_widget.focus()
        
        if self.initialize_slack():
            self.load_channels()
        else:
            self.update_status(
                "Failed to initialize Slack. Check SLACK_BOT_TOKEN in .env file.",
                "error"
            )

    def initialize_slack(self) -> bool:
        try:
            bot_token = os.environ.get("SLACK_BOT_TOKEN")
            if not bot_token:
                self.update_status(
                    "Error: SLACK_BOT_TOKEN not found in environment variables",
                    "error"
                )
                return False
            
            self.slack_app = App(token=bot_token)
            self.update_status("Slack app initialized successfully", "success")
            return True
        except Exception as e:
            self.update_status(f"Error initializing Slack: {e}", "error")
            return False

    @work(exclusive=True, thread=True)
    def load_channels(self) -> None:
        if not self.slack_app:
            self.call_from_thread(self.update_status, "Slack app not initialized", "error")
            return
        
        self.call_from_thread(self.update_status, "Loading channels...", "loading")
        
        try:
            channels = []
            cursor = None
            page_count = 0
            
            while True:
                try:
                    result = self.slack_app.client.conversations_list(
                        types="public_channel",
                        cursor=cursor,
                        limit=200
                    )
                    
                    if not result["ok"]:
                        error_msg = result.get('error', 'Unknown error')
                        
                        # Handle rate limiting
                        if error_msg == "ratelimited":
                            retry_after = int(result.get("headers", {}).get("Retry-After", 1))
                            self.call_from_thread(
                                self.update_status,
                                f"Rate limited. Waiting {retry_after}s... (Loaded {len(channels)} so far)",
                                "loading"
                            )
                            time.sleep(retry_after)
                            continue
                        
                        self.call_from_thread(
                            self.update_status,
                            f"Error fetching channels: {error_msg} (Loaded {len(channels)} so far)",
                            "error"
                        )
                        break
                    
                    batch = result.get("channels", [])
                    channels.extend(batch)
                    page_count += 1
                    
                    # Update progress every 10 pages
                    if page_count % 10 == 0:
                        self.call_from_thread(
                            self.update_status,
                            f"Loading channels... ({len(channels)} loaded so far)",
                            "loading"
                        )
                    
                    # Get next cursor - handle both None and empty string
                    response_metadata = result.get("response_metadata", {})
                    cursor = response_metadata.get("next_cursor")
                    if not cursor or cursor == "":
                        break
                        
                except Exception as e:
                    # Log error but continue if we have channels
                    error_msg = str(e)
                    if "ratelimited" in error_msg.lower() or "rate limit" in error_msg.lower():
                        self.call_from_thread(
                            self.update_status,
                            f"Rate limited. Waiting... (Loaded {len(channels)} so far)",
                            "loading"
                        )
                        time.sleep(2)
                        continue
                    
                    # For other errors, log and break
                    self.call_from_thread(
                        self.update_status,
                        f"Error: {error_msg} (Loaded {len(channels)} channels before error)",
                        "error"
                    )
                    break
            
            self.channels = channels
            self.filtered_channels = channels
            self.call_from_thread(
                self.update_status,
                f"✓ Loaded {len(channels)} channels. Start typing to search.",
                "success"
            )
            
            self.call_from_thread(self.update_suggestions, "")
            
        except Exception as e:
            self.call_from_thread(
                self.update_status,
                f"Error loading channels: {e}",
                "error"
            )

    def update_status(self, message: str, status_type: str = "") -> None:
        status_widget = self.query_one("#status_text", Static)
        status_widget.update(message)
        status_widget.remove_class("loading", "success", "error")
        if status_type:
            status_widget.add_class(status_type)

    def update_suggestions(self, query: str) -> None:
        suggestions_container = self.query_one("#suggestions_container", Container)
        suggestions_list = self.query_one("#suggestions_list", Vertical)
        
        query_lower = query.lower().lstrip('#')
        
        if query_lower:
            self.filtered_channels = [
                ch for ch in self.channels
                if query_lower in ch.get('name', '').lower()
            ]
        else:
            self.filtered_channels = self.channels[:20]  
        
        for label in self.suggestion_labels:
            label.remove()
        self.suggestion_labels.clear()
        
        for channel in self.filtered_channels[:10]:  
            channel_name = channel.get('name', '')
            channel_id = channel.get('id', '')
            label = ChannelLabel(channel_name, channel_id)
            self.suggestion_labels.append(label)
            suggestions_list.mount(label)
        
        if self.filtered_channels and query:
            suggestions_container.add_class("visible")
            self.selected_index = 0
            self.highlight_suggestion()
        else:
            suggestions_container.remove_class("visible")
            self.selected_index = 0

    def highlight_suggestion(self) -> None:
        for i, label in enumerate(self.suggestion_labels):
            if i == self.selected_index:
                label.add_class("--highlight")
            else:
                label.remove_class("--highlight")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "channel_input":
            query = event.value
            self.update_suggestions(query)
            self.selected_index = 0
            self.highlight_suggestion()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message_input":
            message = event.value.strip()
            if message and self.selected_channel_id:
                self.send_message(message)
            return
        
        if event.input.id == "channel_input":
            channel_input = event.input.value.strip()
            
            if not channel_input:
                return
            
            if self.filtered_channels and self.selected_index < len(self.filtered_channels):
                selected_channel = self.filtered_channels[self.selected_index]
                channel_id = selected_channel.get('id')
                channel_name = selected_channel.get('name')
                self.handle_channel_selection(channel_id, channel_name)
                return
            
            channel_name = channel_input.lstrip('#')
            matching_channel = None
            for channel in self.channels:
                if channel.get('name', '').lower() == channel_name.lower():
                    matching_channel = channel
                    break
            
            if matching_channel:
                channel_id = matching_channel.get('id')
                channel_name = matching_channel.get('name')
                self.handle_channel_selection(channel_id, channel_name)
            else:
                self.update_status(f"Channel '#{channel_name}' not found", "error")

    def on_channel_selected(self, event: ChannelSelected) -> None:
        self.handle_channel_selection(event.channel_id, event.channel_name)

    def handle_channel_selection(self, channel_id: str, channel_name: str) -> None:
        self.selected_channel_id = channel_id
        self.selected_channel_name = channel_name
        
        input_container = self.query_one("#input_container", Vertical)
        input_container.display = False
        
        main_container = self.query_one("#main_container", Container)
        message_container = Vertical(id="message_container")
        main_container.mount(message_container)
        
        message_container.mount(
            Static(f"Sending to: #{channel_name}", id="channel_header")
        )
        
        messages_display = RichLog(id="messages_display", highlight=True, markup=True)
        message_container.mount(messages_display)
        
        message_container.mount(
            Input(placeholder="Type your message...", id="message_input")
        )
        message_container.mount(
            Button("← Back to Channels", id="back_button", variant="primary")
        )
        
        self.load_messages(channel_id)
        
        message_input = self.query_one("#message_input", Input)
        message_input.focus()
        
        self.update_status(f"Ready to send message to #{channel_name}", "success")
        
    def action_select_first_suggestion(self) -> None:
        if self.filtered_channels and self.selected_index < len(self.filtered_channels):
            selected_channel = self.filtered_channels[self.selected_index]
            channel_id = selected_channel.get('id')
            channel_name = selected_channel.get('name')
            self.handle_channel_selection(channel_id, channel_name)

    def action_navigate_up(self) -> None:
        if self.suggestion_labels:
            self.selected_index = max(0, self.selected_index - 1)
            self.highlight_suggestion()

    def action_navigate_down(self) -> None:
        if self.suggestion_labels:
            self.selected_index = min(len(self.suggestion_labels) - 1, self.selected_index + 1)
            self.highlight_suggestion()

    @work(exclusive=True, thread=True)
    def refresh_messages_loop(self, channel_id: str) -> None:
        while self.selected_channel_id == channel_id:
            self.load_messages_impl(channel_id)
            time.sleep(1)
    
    @work(exclusive=True, thread=True)
    def load_messages(self, channel_id: str) -> None:
        self.load_messages_impl(channel_id)
        self.refresh_messages_task = self.refresh_messages_loop(channel_id)
    
    def load_messages_impl(self, channel_id: str) -> None:
        if not self.slack_app:
            return
        
        try:
            self.call_from_thread(self.update_status, "Loading messages...", "loading")
            
            result = self.slack_app.client.conversations_history(
                channel=channel_id,
                limit=100
            )
            
            if result["ok"]:
                messages = result.get("messages", [])
                user_ids = set()
                for msg in messages:
                    if "user" in msg:
                        user_ids.add(msg["user"])
                
                if user_ids:
                    try:
                        all_users = []
                        cursor = None
                        while True:
                            users_result = self.slack_app.client.users_list(cursor=cursor, limit=200)
                            if users_result["ok"]:
                                all_users.extend(users_result.get("members", []))
                                cursor = users_result.get("response_metadata", {}).get("next_cursor")
                                if not cursor:
                                    break
                            else:
                                error = users_result.get("error", "unknown")
                                self.call_from_thread(
                                    self.update_status,
                                    f"Warning: Cannot fetch users - {error}",
                                    "error"
                                )
                                break
                        
                        user_map = {}
                        for u in all_users:
                            user_id = u.get("id", "")
                            display_name = (
                                u.get("real_name") or 
                                u.get("profile", {}).get("real_name") or
                                u.get("profile", {}).get("display_name") or
                                u.get("name") or 
                                user_id
                            )
                            user_map[user_id] = display_name
                        for user_id in user_ids:
                            self.user_cache[user_id] = user_map.get(user_id, user_id)
                    except Exception as e:
                        self.call_from_thread(
                            self.update_status,
                            f"Error fetching users: {e}",
                            "error"
                        )
                        for user_id in user_ids:
                            self.user_cache[user_id] = user_id
                
                def display_messages():
                    try:
                        messages_display = self.query_one("#messages_display", RichLog)
                        messages_display.clear()
                        
                        if not messages:
                            messages_display.write("No messages found in this channel.")
                            return
                        
                        for msg in reversed(messages):
                            user_id = msg.get("user", "Unknown")
                            text = msg.get("text", "")
                            
                            user_name = self.user_cache.get(user_id, user_id)
                            messages_display.write(f"[bold cyan]{user_name}[/]: {text}")
                    except Exception as e:
                        pass
                
                self.call_from_thread(display_messages)
                self.call_from_thread(
                    self.update_status,
                    f"✓ Loaded {len(messages)} messages",
                    "success"
                )
            else:
                self.call_from_thread(
                    self.update_status,
                    "Failed to load messages",
                    "error"
                )
        except Exception as e:
            self.call_from_thread(
                self.update_status,
                f"Error loading messages: {e}",
                "error"
            )

    @work(exclusive=True, thread=True)
    def send_message(self, message: str) -> None:
        if not self.slack_app or not self.selected_channel_id:
            self.call_from_thread(self.update_status, "Error: No channel selected", "error")
            return
        
        self.call_from_thread(self.update_status, "Checking channel membership...", "loading")
        
        try:
            membership_result = self.slack_app.client.conversations_info(
                channel=self.selected_channel_id
            )
            
            is_member = membership_result.get("channel", {}).get("is_member", False)
            
            if not is_member:
                self.call_from_thread(self.update_status, "Joining channel...", "loading")
                join_result = self.slack_app.client.conversations_join(
                    channel=self.selected_channel_id
                )
                
                if not join_result["ok"]:
                    error_msg = join_result.get('error', 'Unknown error')
                    self.call_from_thread(
                        self.update_status,
                        f"Failed to join channel: {error_msg}",
                        "error"
                    )
                    return
            
            self.call_from_thread(self.update_status, "Sending message...", "loading")
            
            result = self.slack_app.client.chat_postMessage(
                channel=self.selected_channel_id,
                text=message
            )
            
            if result["ok"]:
                self.call_from_thread(
                    self.update_status,
                    f"✓ Message sent to #{self.selected_channel_name}!",
                    "success"
                )
                def clear_input():
                    message_input = self.query_one("#message_input", Input)
                    message_input.value = ""
                self.call_from_thread(clear_input)
            else:
                error_msg = result.get('error', 'Unknown error')
                self.call_from_thread(
                    self.update_status,
                    f"Failed to send message: {error_msg}",
                    "error"
                )
        except Exception as e:
            self.call_from_thread(
                self.update_status,
                f"Error sending message: {e}",
                "error"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back_button":
            self.return_to_channel_selection()
    
    def return_to_channel_selection(self) -> None:
        self.selected_channel_id = None
        
        try:
            message_container = self.query_one("#message_container", Vertical)
            message_container.remove()
        except Exception:
            pass
        
        input_container = self.query_one("#input_container", Vertical)
        input_container.display = True
        
        channel_input = self.query_one("#channel_input", Input)
        channel_input.value = ""
        channel_input.focus()
        
        self.selected_channel_name = None
        
        self.update_status("Select a channel", "success")

    def on_quit_requested(self, event: QuitRequested) -> None:
        self.action_quit()

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    app = BotCLI()
    app.run()
