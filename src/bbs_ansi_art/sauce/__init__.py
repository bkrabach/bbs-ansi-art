"""SAUCE metadata handling."""

from bbs_ansi_art.sauce.record import SauceRecord
from bbs_ansi_art.sauce.reader import parse_sauce
from bbs_ansi_art.sauce.writer import write_sauce

__all__ = ["SauceRecord", "parse_sauce", "write_sauce"]
