import re
from typing import Tuple


def parse_slack_formatting(text: str, user_cache: dict[str, str] = None, channel_cache: dict[str, str] = None) -> str:
    try:
        if user_cache is None:
            user_cache = {}
        if channel_cache is None:
            channel_cache = {}
        
        def replace_hyperlink_with_label(match):
            url = match.group(1)
            label = match.group(2)
            return f'[link="{url}"][blue]{label}[/blue][/link]'
        text = re.sub(r'<([^|>]+)\|([^>]+)>', replace_hyperlink_with_label, text)
        
        def replace_hyperlink(match):
            url = match.group(1)
            return f'[link="{url}"][blue]{url}[/blue][/link]'
        text = re.sub(r'<(https?://[^>]+)>', replace_hyperlink, text)
        
        def replace_user_mention(match):
            user_id = match.group(1)
            user_name = user_cache.get(user_id, user_id)
            return f'[yellow]@{user_name}[/yellow]'
        text = re.sub(r'<@([A-Z0-9]+)>', replace_user_mention, text)
        
        def replace_channel_mention(match):
            channel_id = match.group(1)
            label = match.group(2)
            if not label:
                label = channel_cache.get(channel_id, channel_id)
            return f'#{label}'
        text = re.sub(r'<#([A-Z0-9]+)\|([^>]*)>', replace_channel_mention, text)
        
        text = re.sub(r'\*(\S.*?\S|\S)\*', r'[bold]\1[/bold]', text)
        
        text = re.sub(r'_(\S.*?\S|\S)_', r'[italic]\1[/italic]', text)
        
        text = re.sub(r'~(\S.*?\S|\S)~', r'[strike]\1[/strike]', text)
        
        return text
    except Exception as e:
        return text


def format_user_input(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
    
    text = re.sub(r'(?<![<\[])(https?://[^\s>]+)', r'<\1>', text)
    
    return text


def resolve_mentions_in_message(text: str, user_name_map: dict[str, str]) -> str:
    reverse_map = {name.lower(): uid for uid, name in user_name_map.items()}
    
    def replace_mention(match):
        username = match.group(1).lower()
        user_id = reverse_map.get(username)
        if user_id:
            return f'<@{user_id}>'
        return match.group(0) 
    text = re.sub(r'@([a-zA-Z0-9_.-]+)', replace_mention, text)
    
    return text
