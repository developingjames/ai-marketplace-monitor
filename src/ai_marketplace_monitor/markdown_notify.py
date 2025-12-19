import re
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import ClassVar, List

from .ai import AIResponse  # type: ignore
from .listing import Listing
from .notification import NotificationStatus, PushNotificationConfig
from .utils import hilight


@dataclass
class MarkdownNotificationConfig(PushNotificationConfig):
    notify_method = "markdown"
    required_fields: ClassVar[List[str]] = ["markdown_output_dir"]

    markdown_output_dir: str | None = None
    markdown_filename_format: str | None = None
    markdown_include_frontmatter: bool | None = None
    markdown_overwrite_existing: bool | None = None

    def handle_markdown_output_dir(self: "MarkdownNotificationConfig") -> None:
        if self.markdown_output_dir is None:
            return

        if not isinstance(self.markdown_output_dir, str):
            raise ValueError("markdown_output_dir must be a string")

        # Expand user home directory
        self.markdown_output_dir = str(Path(self.markdown_output_dir).expanduser())

    def handle_markdown_filename_format(self: "MarkdownNotificationConfig") -> None:
        if self.markdown_filename_format is None:
            self.markdown_filename_format = "{marketplace}_{id}"

        if not isinstance(self.markdown_filename_format, str):
            raise ValueError("markdown_filename_format must be a string")

        # Validate that placeholders are recognized
        valid_placeholders = {"{marketplace}", "{id}", "{timestamp}", "{title}", "{name}"}
        # Extract all placeholders from the format string
        placeholders = set(re.findall(r"\{[^}]+\}", self.markdown_filename_format))
        invalid = placeholders - valid_placeholders
        if invalid:
            raise ValueError(
                f"Invalid filename format placeholders: {invalid}. "
                f"Valid placeholders are: {valid_placeholders}"
            )

    def handle_markdown_include_frontmatter(self: "MarkdownNotificationConfig") -> None:
        if self.markdown_include_frontmatter is None:
            self.markdown_include_frontmatter = False

        if not isinstance(self.markdown_include_frontmatter, bool):
            raise ValueError("markdown_include_frontmatter must be a boolean")

    def handle_markdown_overwrite_existing(self: "MarkdownNotificationConfig") -> None:
        if self.markdown_overwrite_existing is None:
            self.markdown_overwrite_existing = False

        if not isinstance(self.markdown_overwrite_existing, bool):
            raise ValueError("markdown_overwrite_existing must be a boolean")

    def _sanitize_filename(self: "MarkdownNotificationConfig", filename: str) -> str:
        """Remove invalid filesystem characters and limit length"""
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove any leading/trailing whitespace or dots
        sanitized = sanitized.strip(". ")
        # Limit length (255 is typical filesystem limit, leave room for .md extension)
        if len(sanitized) > 250:
            sanitized = sanitized[:250]
        return sanitized

    def _format_listing_as_markdown(
        self: "MarkdownNotificationConfig",
        listing: Listing,
        rating: AIResponse,
        notification_status: NotificationStatus,
    ) -> str:
        """Generate markdown content from listing data"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content_parts = []

        # Add YAML frontmatter if requested
        if self.markdown_include_frontmatter:
            frontmatter = [
                "---",
                f'marketplace: "{listing.marketplace}"',
                f'id: "{listing.id}"',
                f'title: "{listing.title.replace(chr(34), chr(39))}"',  # Escape quotes
                f'price: "{listing.price}"',
                f'location: "{listing.location}"',
                f'seller: "{listing.seller}"',
                f'condition: "{listing.condition}"',
                f"url: {listing.post_url.split('?')[0]}",
                f'found_date: "{timestamp}"',
                f'item_name: "{listing.name}"',
            ]

            # Add AI evaluation to frontmatter if available
            if rating.comment != AIResponse.NOT_EVALUATED:
                frontmatter.extend(
                    [
                        f"ai_score: {rating.score}",
                        f'ai_conclusion: "{rating.conclusion}"',
                    ]
                )

            frontmatter.append("---")
            content_parts.append("\n".join(frontmatter))
            content_parts.append("")  # Blank line after frontmatter

        # Title
        content_parts.append(f"# {listing.title}")
        content_parts.append("")

        # Metadata section
        if not self.markdown_include_frontmatter:
            # If no frontmatter, include metadata in body
            content_parts.extend(
                [
                    f"**Marketplace:** {listing.marketplace}",
                    f"**Item ID:** {listing.id}",
                ]
            )

        content_parts.extend(
            [
                f"**Price:** {listing.price}",
                f"**Location:** {listing.location}",
                f"**Seller:** {listing.seller}",
                f"**Condition:** {listing.condition}",
            ]
        )

        if not self.markdown_include_frontmatter:
            content_parts.append(f"**Found:** {timestamp}")

        content_parts.append("")
        content_parts.append(f"[View Listing]({listing.post_url.split('?')[0]})")
        content_parts.append("")

        # Image if available
        if listing.image:
            content_parts.append(f"![Listing Image]({listing.image})")
            content_parts.append("")

        # Description
        if listing.description:
            content_parts.append("## Description")
            content_parts.append("")
            content_parts.append(listing.description)
            content_parts.append("")

        # AI Evaluation
        if rating.comment != AIResponse.NOT_EVALUATED:
            content_parts.append("## AI Evaluation")
            content_parts.append("")
            content_parts.append(f"**Rating:** {rating.conclusion} ({rating.score}/5)")
            content_parts.append("")
            content_parts.append(rating.comment)
            content_parts.append("")

        # Footer
        content_parts.append("---")
        content_parts.append("")
        content_parts.append(f"*Found by AI Marketplace Monitor on {timestamp}*")

        return "\n".join(content_parts)

    def notify(
        self: "MarkdownNotificationConfig",
        listings: List[Listing],
        ratings: List[AIResponse],
        notification_status: List[NotificationStatus],
        force: bool = False,
        logger: Logger | None = None,
    ) -> bool:
        """Write markdown files for each listing"""
        if not self._has_required_fields():
            if logger:
                logger.debug(
                    f"Missing required fields {', '.join(self.required_fields)}. "
                    f"No {self.notify_method} notification sent."
                )
            return False

        # Create output directory
        try:
            output_path = Path(self.markdown_output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            if logger:
                logger.error(f"""{hilight("[Markdown]", "fail")} Failed to create output directory: {e}""")
            return False

        # Track how many files we successfully write
        files_written = 0
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for listing, rating, ns in zip(listings, ratings, notification_status):
            # Skip already-notified listings unless force is True
            if ns == NotificationStatus.NOTIFIED and not force:
                continue

            # Skip if file exists and we're not overwriting
            # Generate filename
            filename_base = self.markdown_filename_format.format(
                marketplace=listing.marketplace,
                id=listing.id,
                timestamp=timestamp,
                title=self._sanitize_filename(listing.title[:50]),  # Limit title length
                name=listing.name,
            )
            filename = self._sanitize_filename(filename_base) + ".md"
            filepath = output_path / filename

            # Check if file exists and skip if not overwriting
            if filepath.exists() and not self.markdown_overwrite_existing and not force:
                if logger:
                    logger.debug(
                        f"""{hilight("[Markdown]", "info")} Skipping existing file: {filename}"""
                    )
                continue

            # Generate markdown content
            try:
                markdown_content = self._format_listing_as_markdown(listing, rating, ns)

                # Write to file
                filepath.write_text(markdown_content, encoding="utf-8")
                files_written += 1

                if logger:
                    logger.info(
                        f"""{hilight("[Markdown]", "succ")} Wrote markdown file: {hilight(filename)}"""
                    )

            except Exception as e:
                if logger:
                    logger.error(
                        f"""{hilight("[Markdown]", "fail")} Failed to write {filename}: {e}"""
                    )
                continue

        if files_written > 0:
            if logger:
                logger.info(
                    f"""{hilight("[Markdown]", "succ")} Successfully wrote {files_written} markdown file(s) to {hilight(str(output_path))}"""
                )
            return True
        else:
            if logger:
                logger.debug("No new markdown files to write.")
            return False
