"""Analytics viewer rendering for playlist analytics."""

import sys
from blessed import Terminal
from ..state import UIState

# Layout constants
ANALYTICS_VIEWER_HEADER_LINES = 2  # Title + help line
ANALYTICS_VIEWER_FOOTER_LINES = 1


def format_analytics_lines(analytics: dict, term: Terminal) -> list[str]:
    """
    Format analytics data into colored terminal lines.

    Args:
        analytics: Analytics data dictionary
        term: blessed Terminal instance

    Returns:
        List of formatted terminal strings
    """
    lines = []

    # Header
    header = f"📊 \"{analytics['playlist_name']}\" Analytics ({analytics['playlist_type']})"
    lines.append(term.bold_cyan(header))
    lines.append(term.cyan("═" * min(70, term.width - 4)))
    lines.append("")

    # Basic Stats
    if 'basic' in analytics:
        basic = analytics['basic']
        if basic['total_tracks'] > 0:
            lines.append(term.bold_yellow("📈 BASIC STATS"))
            total_secs = int(basic['total_duration'])
            hours = total_secs // 3600
            minutes = (total_secs % 3600) // 60
            seconds = total_secs % 60
            avg_secs = int(basic['avg_duration'])
            avg_mins = avg_secs // 60
            avg_secs_rem = avg_secs % 60

            lines.append(f"  Tracks: " + term.bold_white(str(basic['total_tracks'])))
            lines.append(f"  Duration: " + term.bold_white(f"{hours}h {minutes}m {seconds}s") + f" (avg: {avg_mins}m {avg_secs_rem}s)")
            if basic['year_min'] and basic['year_max']:
                lines.append(f"  Year Range: " + term.bold_white(f"{basic['year_min']}-{basic['year_max']}"))
            lines.append("")

    # Artist Analysis with bar charts
    if 'artists' in analytics:
        artists = analytics['artists']
        if artists['top_artists']:
            lines.append(term.bold_yellow("🎤 TOP ARTISTS"))
            top_artists = artists['top_artists'][:10]
            max_count = max(a['track_count'] for a in top_artists) if top_artists else 0

            for artist_data in top_artists:
                artist_name = artist_data['artist'][:20]
                count = artist_data['track_count']
                filled_width = int((count / max_count) * 12) if max_count > 0 else 0
                bar = '▓' * filled_width + '░' * (12 - filled_width)
                percentage = (count / basic['total_tracks'] * 100) if basic['total_tracks'] > 0 else 0
                lines.append(f"  {artist_name:20s} {bar} " + term.bold_cyan(f"{count:3d}") + f" ({percentage:.1f}%)")

            lines.append(term.white(f"  Total: {artists['total_unique_artists']} unique artists (avg: {artists['diversity_ratio']:.1f} tracks/artist)"))
            lines.append("")

    # Genre Distribution
    if 'genres' in analytics:
        genres = analytics['genres']['genres']
        if genres:
            lines.append(term.bold_yellow("🎵 GENRE DISTRIBUTION"))
            top_genres = genres[:10]
            max_count = max(g['count'] for g in top_genres) if top_genres else 0

            for genre_data in top_genres:
                genre = genre_data['genre'][:20]
                count = genre_data['count']
                percentage = genre_data['percentage']
                filled_width = int((count / max_count) * 12) if max_count > 0 else 0
                bar = '▓' * filled_width + '░' * (12 - filled_width)
                lines.append(f"  {genre:20s} {bar} " + term.bold_magenta(f"{count:3d}") + f" ({percentage:.1f}%)")

            if len(genres) > 10:
                lines.append(term.white(f"  ... and {len(genres) - 10} more"))
            lines.append("")

    # Tag Analysis
    if 'tags' in analytics:
        tags = analytics['tags']
        if tags['top_ai_tags'] or tags['top_user_tags']:
            lines.append(term.bold_yellow("#️⃣ TOP TAGS"))

            if tags['top_ai_tags']:
                lines.append("  AI Tags:")
                for tag in tags['top_ai_tags'][:10]:
                    avg_conf = tag.get('avg_confidence')
                    if avg_conf is not None:
                        lines.append(f"    • {tag['tag_name']} ({tag['count']}) - conf: {avg_conf:.2f}")
                    else:
                        lines.append(f"    • {tag['tag_name']} ({tag['count']})")

            if tags['top_user_tags']:
                lines.append("  User Tags:")
                for tag in tags['top_user_tags'][:10]:
                    lines.append(f"    • {tag['tag_name']} ({tag['count']})")

            if tags['top_file_tags']:
                lines.append("  File Tags:")
                for tag in tags['top_file_tags'][:10]:
                    lines.append(f"    • {tag['tag_name']} ({tag['count']})")
            lines.append("")

    # BPM Analysis
    if 'bpm' in analytics:
        bpm = analytics['bpm']
        if bpm['min'] is not None:
            lines.append(term.bold_yellow("⚡ BPM ANALYSIS"))
            lines.append(f"  Range: " + term.bold_white(f"{bpm['min']:.0f}-{bpm['max']:.0f} BPM") + f" (avg: {bpm['avg']:.0f}, median: {bpm['median']:.0f})")
            lines.append("  Distribution:")

            max_count = max(bpm['distribution'].values()) if bpm['distribution'] else 0
            for range_name, count in bpm['distribution'].items():
                if count > 0:
                    filled_width = int((count / max_count) * 15) if max_count > 0 else 0
                    bar = '▓' * filled_width + '░' * (15 - filled_width)
                    peak_marker = " ← Peak" if count == max_count else ""
                    style = term.bold_green if count == max_count else term.white
                    lines.append(style(f"    {range_name:8s} │ {count:3d}  {bar}{peak_marker}"))
            lines.append("")

    # Key Distribution
    if 'keys' in analytics:
        keys = analytics['keys']
        if keys['top_keys']:
            lines.append(term.bold_yellow("🔑 KEY DISTRIBUTION"))
            lines.append(f"  Total: {keys['total_unique_keys']} unique keys")
            lines.append("  Most Common:")
            for key_data in keys['top_keys'][:10]:
                lines.append(f"    • {key_data['key_signature']}: {key_data['count']} tracks")
            lines.append(f"  Harmonic pairs: {keys['harmonic_pairs_count']} compatible transitions")
            lines.append("")

    # Year Distribution
    if 'years' in analytics:
        years = analytics['years']
        lines.append(term.bold_yellow("📅 YEAR DISTRIBUTION"))
        lines.append("  By Decade:")
        for decade, count in years['decade_distribution'].items():
            if count > 0:
                lines.append(f"    {decade}: {count} tracks")
        lines.append(f"  Recent (2020+): {years['recent_count']} tracks ({years['recent_percentage']:.1f}%)")
        lines.append(f"  Classic (pre-2020): {years['classic_count']} tracks")
        lines.append("")

    # Rating Analysis
    if 'ratings' in analytics:
        ratings = analytics['ratings']
        if ratings['rating_counts']:
            lines.append(term.bold_yellow("⭐ RATING ANALYSIS"))
            for rating_type, count in ratings['rating_counts'].items():
                lines.append(f"  {rating_type.capitalize()}: {count} tracks")

            if ratings['most_loved_tracks']:
                lines.append("  Most Loved:")
                for i, track in enumerate(ratings['most_loved_tracks'][:5], 1):
                    lines.append(f"    {i}. {track['artist']} - {track['title']}")
            lines.append("")

    # Quality Metrics
    if 'quality' in analytics:
        quality = analytics['quality']
        lines.append(term.bold_yellow("✅ QUALITY METRICS"))

        # Color-coded completeness score
        completeness = quality['completeness_score']
        filled_width = int(completeness / 100 * 20)
        bar = '▓' * filled_width + '░' * (20 - filled_width)

        if completeness >= 80:
            quality_color = term.bold_green
            status_icon = "🟢"
        elif completeness >= 50:
            quality_color = term.bold_yellow
            status_icon = "🟡"
        else:
            quality_color = term.bold_red
            status_icon = "🔴"

        lines.append(f"  Completeness: {bar} {quality_color(f'{completeness:.1f}%')} {status_icon}")

        total = quality['total_tracks']
        if total > 0:
            missing_fields = []
            if quality['missing_bpm'] > 0:
                pct = quality['missing_bpm'] / total * 100
                missing_fields.append(('BPM', quality['missing_bpm'], pct))
            if quality['missing_key'] > 0:
                pct = quality['missing_key'] / total * 100
                missing_fields.append(('Key', quality['missing_key'], pct))
            if quality['missing_year'] > 0:
                pct = quality['missing_year'] / total * 100
                missing_fields.append(('Year', quality['missing_year'], pct))
            if quality['missing_genre'] > 0:
                pct = quality['missing_genre'] / total * 100
                missing_fields.append(('Genre', quality['missing_genre'], pct))
            if quality['without_tags'] > 0:
                pct = quality['without_tags'] / total * 100
                missing_fields.append(('Tags', quality['without_tags'], pct))

            if missing_fields:
                lines.append(term.white("  Missing Metadata:"))
                for field_name, count, pct in missing_fields:
                    filled_width = int((100 - pct) / 100 * 10)
                    bar = '█' * filled_width + '─' * (10 - filled_width)
                    if pct > 20:
                        color = term.red
                    elif pct > 5:
                        color = term.yellow
                    else:
                        color = term.white
                    lines.append(f"    {field_name:6s}: {bar} {color(f'{count} tracks ({pct:.1f}%)')}")
        lines.append("")

    lines.append(term.white("─" * min(70, term.width - 4)))

    return lines


def render_analytics_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render analytics viewer with scrolling support.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for viewer
    """
    if not state.analytics_viewer_visible or height <= 0:
        return

    analytics = state.analytics_viewer_data
    scroll_offset = state.analytics_viewer_scroll

    # Format all analytics lines
    all_lines = format_analytics_lines(analytics, term)

    # Reserve lines for header and footer
    content_height = height - ANALYTICS_VIEWER_FOOTER_LINES

    # Calculate visible window
    visible_lines = all_lines[scroll_offset:scroll_offset + content_height]

    # Render visible lines
    for i, line in enumerate(visible_lines):
        if i < content_height:
            sys.stdout.write(term.move_xy(0, y + i) + line + term.clear_eol)

    # Clear remaining lines
    for i in range(len(visible_lines), content_height):
        sys.stdout.write(term.move_xy(0, y + i) + term.clear_eol)

    # Footer help text
    footer_y = y + height - ANALYTICS_VIEWER_FOOTER_LINES
    help_text = "[j/k: scroll] [q/Esc: close]"
    scroll_info = f"Line {scroll_offset + 1}/{len(all_lines)}" if all_lines else ""

    # Left-align help, right-align scroll info
    help_x = 2
    scroll_x = max(help_x + len(help_text) + 4, term.width - len(scroll_info) - 2)

    sys.stdout.write(term.move_xy(help_x, footer_y) + term.bold_white(help_text))
    if scroll_info:
        sys.stdout.write(term.move_xy(scroll_x, footer_y) + term.white(scroll_info))
