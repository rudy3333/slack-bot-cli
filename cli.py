
import os
import re
import time
import json
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, ".cache")
CHANNELS_CACHE_FILE = os.path.join(CACHE_DIR, "channels_cache.json")

os.makedirs(CACHE_DIR, exist_ok=True)


class ChannelLabel(Label):
    def __init__(self, channel_name: str, channel_id: str):
        super().__init__()
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.update(f"#{channel_name} ({channel_id})")
    
    def on_click(self) -> None:
        self.post_message(ChannelSelected(self.channel_id, self.channel_name))


class MemberLabel(Label):
    def __init__(self, user_name: str, user_id: str):
        super().__init__()
        self.user_name = user_name
        self.user_id = user_id
        self.update(f"@{user_name}")
    
    def on_click(self) -> None:
        self.post_message(MemberSelected(self.user_id, self.user_name))


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


class MemberSelected(Message):
    def __init__(self, user_id: str, user_name: str):
        super().__init__()
        self.user_id = user_id
        self.user_name = user_name


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
        height: 20;
        border: solid $primary;
        margin-top: 1;
        padding: 1;
        display: none;
    }
    
    #suggestions_container.visible {
        display: block;
    }
    
    #suggestions_list {
        height: auto;
        width: 100%;
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
    
    #join_container {
        height: 20;
        width: 80;
        layout: vertical;
        align: center middle;
        content-align: center middle;
    }
    
    #join_channel_button {
        width: 25;
    }
    
    #members_container {
        width: 80;
        height: 10;
        border: solid $accent;
        margin-bottom: 1;
        padding: 1;
        display: none;
    }
    
    #members_container.visible {
        display: block;
    }
    
    #members_list {
        height: auto;
        width: 100%;
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
        self.last_message_ts: Optional[str] = None
        self.channel_members: dict[str, list[dict]] = {}
        self.member_labels: list[MemberLabel] = []
        self.member_selected_index: int = 0
        self.mention_at_position: int = 0
        self.channels_loaded: bool = False
        self.refresh_channels_task = None

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
                
                with ScrollableContainer(id="suggestions_container"):
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
    
    def save_channels_cache(self) -> None:
        try:
            with open(CHANNELS_CACHE_FILE, 'w') as f:
                json.dump(self.channels, f, indent=2)
        except Exception:
            pass
    
    def load_channels_cache(self) -> bool:
        try:
            if os.path.exists(CHANNELS_CACHE_FILE):
                with open(CHANNELS_CACHE_FILE, 'r') as f:
                    self.channels = json.load(f)
                    self.filtered_channels = self.channels
                    return True
        except Exception:
            pass
        return False

    @work(exclusive=True, thread=True)
    def refresh_channels_loop(self) -> None:
        while True:
            time.sleep(30)
            if self.slack_app and self.channels_loaded:
                self._fetch_channels_impl()
    
    @work(exclusive=True, thread=True)
    def load_channels(self) -> None:
        if not self.slack_app:
            self.call_from_thread(self.update_status, "Slack app not initialized", "error")
            return
        
        if self.load_channels_cache():
            self.channels_loaded = True
            self.call_from_thread(
                self.update_status,
                f"✓ Loaded {len(self.channels)} channels from cache. Updating...",
                "success"
            )
            self.call_from_thread(self.update_suggestions, "")
        else:
            self.call_from_thread(self.update_status, "Loading channels...", "loading")
        
        self._fetch_channels_impl()
        
        if not self.refresh_channels_task:
            self.refresh_channels_task = self.refresh_channels_loop()
    
    def _fetch_channels_impl(self) -> None:
        if not self.slack_app:
            return
        
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
                            if not self.channels_loaded:
                                self.call_from_thread(
                                    self.update_status,
                                    f"Rate limited. Waiting {retry_after}s... (Loaded {len(channels)} so far)",
                                    "loading"
                                )
                            time.sleep(retry_after)
                            continue
                        
                        if not self.channels_loaded:
                            self.call_from_thread(
                                self.update_status,
                                f"Error fetching channels: {error_msg} (Loaded {len(channels)} so far)",
                                "error"
                            )
                        break
                    
                    batch = result.get("channels", [])
                    channels.extend(batch)
                    page_count += 1
                    
                    if not self.channels_loaded and page_count % 10 == 0:
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
                        if not self.channels_loaded:
                            self.call_from_thread(
                                self.update_status,
                                f"Rate limited. Waiting... (Loaded {len(channels)} so far)",
                                "loading"
                            )
                        time.sleep(2)
                        continue
                    
                    # For other errors, log and break
                    if not self.channels_loaded:
                        self.call_from_thread(
                            self.update_status,
                            f"Error: {error_msg} (Loaded {len(channels)} channels before error)",
                            "error"
                        )
                    break
            
            self.channels = channels
            self.filtered_channels = channels
            self.save_channels_cache()
            
            if not self.channels_loaded:
                self.channels_loaded = True
                self.call_from_thread(
                    self.update_status,
                    f"✓ Loaded {len(channels)} channels. Start typing to search.",
                    "success"
                )
                self.call_from_thread(self.update_suggestions, "")
            else:
                self.call_from_thread(
                    self.update_status,
                    f"✓ Updated {len(channels)} channels",
                    "success"
                )
             
        except Exception as e:
            if not self.channels_loaded:
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
        suggestions_container = self.query_one("#suggestions_container", ScrollableContainer)
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
        
        for channel in self.filtered_channels[:50]:  
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
                label.scroll_visible()
            else:
                label.remove_class("--highlight")
    
    def update_member_suggestions(self, query: str, at_position: int) -> None:
        self.mention_at_position = at_position
        
        if not self.selected_channel_id or self.selected_channel_id not in self.channel_members:
            self.load_channel_members(self.selected_channel_id)
            return
        
        members = self.channel_members.get(self.selected_channel_id, [])
        query_lower = query.lower()
        
        filtered_members = [
            m for m in members
            if query_lower in m.get('name', '').lower()
        ][:10]
        
        try:
            members_container = self.query_one("#members_container", ScrollableContainer)
        except:
            try:
                message_input = self.query_one("#message_input", Input)
                message_container = self.query_one("#message_container", Vertical)
                members_container = ScrollableContainer(id="members_container")
                members_list = Vertical(id="members_list")
                message_container.mount(members_container, before=message_input)
                members_container.mount(members_list)
            except:
                return
        
        try:
            members_list = self.query_one("#members_list", Vertical)
        except:
            return
        
        for label in self.member_labels:
            label.remove()
        self.member_labels.clear()
        
        for member in filtered_members:
            label = MemberLabel(member['name'], member['id'])
            label.styles.padding = (0, 1)
            label.styles.height = 1
            self.member_labels.append(label)
            members_list.mount(label)
        
        if filtered_members:
            members_container.add_class("visible")
            self.member_selected_index = 0
            self.highlight_member_suggestion()
        else:
            members_container.remove_class("visible")
    
    def hide_member_suggestions(self) -> None:
        try:
            members_container = self.query_one("#members_container", ScrollableContainer)
            members_container.remove_class("visible")
        except:
            pass
        self.member_labels.clear()
    
    def highlight_member_suggestion(self) -> None:
        for i, label in enumerate(self.member_labels):
            if i == self.member_selected_index:
                label.add_class("--highlight")
                label.scroll_visible()
            else:
                label.remove_class("--highlight")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "channel_input":
            query = event.value
            self.update_suggestions(query)
            self.selected_index = 0
            self.highlight_suggestion()
        elif event.input.id == "message_input":
            text = event.value
            last_word_start = text.rfind('@')
            if last_word_start != -1 and last_word_start < len(text) - 1:
                query = text[last_word_start + 1:]
                if ' ' not in query:
                    self.update_member_suggestions(query, last_word_start)
            else:
                self.hide_member_suggestions()

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
    
    def on_member_selected(self, event: MemberSelected) -> None:
        try:
            message_input = self.query_one("#message_input", Input)
            current_text = message_input.value
            
            before_mention = current_text[:self.mention_at_position]
            mention_text = f"<@{event.user_id}>"
            after_mention = " "
            
            message_input.value = before_mention + mention_text + after_mention
            message_input.cursor_position = len(before_mention + mention_text + after_mention)
            
            self.hide_member_suggestions()
        except Exception as e:
            pass

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
        self.load_channel_members(channel_id)
        
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
    
    def resolve_user_name(self, user_id: str) -> str:
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        
        if not self.slack_app:
            self.user_cache[user_id] = user_id
            return user_id
        
        try:
            result = self.slack_app.client.users_info(user=user_id)
            if result.get("ok"):
                user = result.get("user", {})
                display_name = (
                    user.get("real_name") or 
                    user.get("profile", {}).get("real_name") or
                    user.get("profile", {}).get("display_name") or
                    user.get("name") or 
                    user_id
                )
                self.user_cache[user_id] = display_name
                return display_name
            else:
                self.user_cache[user_id] = user_id
                return user_id
        except Exception as e:
            self.user_cache[user_id] = user_id
            return user_id
    
    def resolve_mentions_in_text(self, text: str) -> str:
        def replace_mention(match):
            user_id = match.group(1)
            user_name = self.resolve_user_name(user_id)
            return f"[yellow]@{user_name}[/yellow]"
        
        return re.sub(r'<@([A-Z0-9]+)>', replace_mention, text)
    
    def resolve_links_in_text(self, text: str) -> str:
        def replace_link(match):
            url = match.group(1)
            display_text = match.group(2) if match.group(2) else url
            return f"[blue link={url}]{display_text}[/blue link]"
        
        return re.sub(r'<([^|>]+)\|([^>]*)>', replace_link, text)
    
    def resolve_formatting(self, text: str) -> str:
        # Code blocks
        text = re.sub(r'```(.*?)```', r'[dim]\1[/dim]', text, flags=re.DOTALL)
        
        # Inline code
        text = re.sub(r'`([^`]+)`', r'[code]\1[/code]', text)
        
        # Bold
        text = re.sub(r'\*([^*]+)\*', r'[bold]\1[/bold]', text)
        
        # Italic
        text = re.sub(r'_([^_]+)_', r'[italic]\1[/italic]', text)
        
        # Strikethrough
        text = re.sub(r'~([^~]+)~', r'[strike]\1[/strike]', text)
        
        return text
    
    def resolve_text(self, text: str) -> str:
        text = self.resolve_mentions_in_text(text)
        text = self.resolve_links_in_text(text)
        text = self.resolve_formatting(text)
        return text
    
    def indent_multiline_text(self, text: str, indent_width: int) -> str:
        lines = text.split('\n')
        if len(lines) <= 1:
            return text
        
        indent = ' ' * indent_width
        return lines[0] + '\n' + '\n'.join(indent + line for line in lines[1:])
    
    @work(exclusive=True, thread=True)
    def load_channel_members(self, channel_id: str) -> None:
        if not self.slack_app or channel_id in self.channel_members:
            return
        
        try:
            members = []
            cursor = None
            
            while True:
                result = self.slack_app.client.conversations_members(
                    channel=channel_id,
                    cursor=cursor,
                    limit=200
                )
                
                if not result.get("ok"):
                    break
                
                batch = result.get("members", [])
                members.extend(batch)
                
                response_metadata = result.get("response_metadata", {})
                cursor = response_metadata.get("next_cursor")
                if not cursor or cursor == "":
                    break
            
            member_list = []
            for user_id in members:
                user_name = self.resolve_user_name(user_id)
                member_list.append({"id": user_id, "name": user_name})
            
            self.channel_members[channel_id] = member_list
        except Exception:
            pass
    
    def load_messages_impl(self, channel_id: str) -> None:
        if not self.slack_app:
            return
        
        try:
            self.call_from_thread(self.update_status, "Checking channel membership...", "loading")
            
            membership_result = self.slack_app.client.conversations_info(
                channel=channel_id
            )
            
            is_member = membership_result.get("channel", {}).get("is_member", False)
            
            if not is_member:
                def show_join_button():
                    try:
                        messages_display = self.query_one("#messages_display", RichLog)
                        messages_display.clear()
                        messages_display.write("Bot is not a member of this channel.")
                    except Exception:
                        pass
                    
                    try:
                        try:
                            old_input = self.query_one("#message_input", Input)
                            old_input.remove()
                        except Exception:
                            pass
                        
                        try:
                            old_container = self.query_one("#join_container", Container)
                            old_container.remove()
                        except Exception:
                            pass
                        
                        message_container = self.query_one("#message_container", Vertical)
                        join_container = Vertical(id="join_container")
                        join_btn = Button("Join Channel", id="join_channel_button", variant="primary")
                        message_container.mount(join_container)
                        join_container.mount(join_btn)
                    except Exception:
                        pass
                
                self.call_from_thread(show_join_button)
                self.call_from_thread(
                    self.update_status,
                    "Bot is not a member. Click 'Join Channel' button.",
                    "error"
                )
                return
            
            self.call_from_thread(self.update_status, "Loading messages...", "loading")
            
            result = self.slack_app.client.conversations_history(
                channel=channel_id,
                limit=100
            )
            
            if result["ok"]:
                messages = result.get("messages", [])
                user_ids = set()
                for msg in messages:
                    user_id = msg.get("user")
                    if user_id:
                        user_ids.add(user_id)
                
                # Resolve user names for all users
                for user_id in user_ids:
                    if user_id not in self.user_cache:
                        self.resolve_user_name(user_id)
                
                def display_messages():
                    try:
                        messages_display = self.query_one("#messages_display", RichLog)
                        
                        # Initial load: clear and display all messages
                        if self.last_message_ts is None:
                            messages_display.clear()
                            
                            if not messages:
                                messages_display.write("No messages found in this channel.")
                                if messages:
                                    self.last_message_ts = messages[0].get("ts")
                                return
                            
                            for msg in reversed(messages):
                                user_id = msg.get("user", "Unknown")
                                text = msg.get("text", "")
                                text = self.resolve_text(text)
                                
                                user_name = self.user_cache.get(user_id, user_id)
                                indent_width = len(user_name) + 2  # username + ": "
                                text = self.indent_multiline_text(text, indent_width)
                                messages_display.write(f"[bold cyan]{user_name}[/]: {text}")
                            
                            if messages:
                                self.last_message_ts = messages[0].get("ts")
                        else:
                            # Only append new messages
                            for msg in reversed(messages):
                                msg_ts = msg.get("ts")
                                if msg_ts and msg_ts > self.last_message_ts:
                                    user_id = msg.get("user", "Unknown")
                                    text = msg.get("text", "")
                                    text = self.resolve_text(text)
                                    user_name = self.user_cache.get(user_id, user_id)
                                    indent_width = len(user_name) + 2  # username + ": "
                                    text = self.indent_multiline_text(text, indent_width)
                                    messages_display.write(f"[bold cyan]{user_name}[/]: {text}")
                                    self.last_message_ts = msg_ts
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
        elif event.button.id == "join_channel_button":
            self.join_channel()
    
    @work(exclusive=True, thread=True)
    def join_channel(self) -> None:
        if not self.slack_app or not self.selected_channel_id:
            self.call_from_thread(self.update_status, "Error: No channel selected", "error")
            return
        
        self.call_from_thread(self.update_status, "Joining channel...", "loading")
        
        try:
            result = self.slack_app.client.conversations_join(
                channel=self.selected_channel_id
            )
            
            if result["ok"]:
                def clean_ui():
                    try:
                        join_container = self.query_one("#join_container", Vertical)
                        join_container.remove()
                    except Exception:
                        pass
                    
                    try:
                        # Try to focus existing message input or create new one
                        try:
                            message_input = self.query_one("#message_input", Input)
                            message_input.focus()
                        except:
                            # If doesn't exist, create it
                            message_container = self.query_one("#message_container", Vertical)
                            message_input = Input(placeholder="Type your message...", id="message_input")
                            # Insert before back button
                            try:
                                back_btn = self.query_one("#back_button", Button)
                                message_container.mount(message_input, before=back_btn)
                            except:
                                message_container.mount(message_input)
                            message_input.focus()
                    except Exception as e:
                        pass
                
                self.call_from_thread(clean_ui)
                self.call_from_thread(self.update_status, "Joined! Loading messages...", "loading")
                # Reload messages now that bot is a member
                self.load_messages_impl(self.selected_channel_id)
            else:
                error_msg = result.get('error', 'Unknown error')
                self.call_from_thread(
                    self.update_status,
                    f"Failed to join channel: {error_msg}",
                    "error"
                )
        except Exception as e:
            self.call_from_thread(
                self.update_status,
                f"Error joining channel: {e}",
                "error"
            )
    
    def return_to_channel_selection(self) -> None:
        self.selected_channel_id = None
        self.last_message_ts = None
        
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
