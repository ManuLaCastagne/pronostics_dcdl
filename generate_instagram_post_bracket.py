from pathlib import Path
import json
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "outputs" / "csv" / "bracket_post_ready.csv"
OUTPUT_FILE = BASE_DIR / "outputs" / "images" / "instagram_results_bracket.png"

WIDTH = 1080
HEIGHT = 1350

TOP_N = 8
START_RANK = 1

RUNTIME_CONFIG_FILE = BASE_DIR / "data" / "runtime_config.json"

DEFAULT_TITLE = "Probabilité de victoire"
DEFAULT_SUBTITLE = ""

BACKGROUND_COLOR = (14, 17, 24)
HEADER_COLOR = (24, 28, 38)
TEXT_COLOR = (255, 255, 255)
SUBTEXT_COLOR = (215, 220, 228)
MUTED_TEXT_COLOR = (180, 188, 200)

BACKGROUND_IMAGE = BASE_DIR / "assets" / "backgrounds" / "plateau.png"
BACKGROUND_OVERLAY = (0, 0, 0, 90)

CARD_X = 36
CARD_W = WIDTH - 72
CARD_H = 125
CARD_GAP = 14
CARDS_START_Y = 175
CARD_RADIUS = 24

PHOTO_SIZE = 90

DEFAULT_PHOTO = BASE_DIR / "assets" / "players" / "default.png"
DEFAULT_FLAG = BASE_DIR / "assets" / "flags" / "default.png"
DEFAULT_CLUB = BASE_DIR / "assets" / "clubs" / "default.png"
LOGO_FILE = BASE_DIR / "assets" / "icons" / "default.png"

FONT_DIR = BASE_DIR / "assets" / "fonts"
FONT_PERCENT = FONT_DIR / "Anton-Regular.ttf"
FONT_TITLE = FONT_DIR / "Montserrat-ExtraBoldItalic.ttf"
FONT_BOLD = FONT_DIR / "Montserrat-Bold.ttf"
FONT_SEMIBOLD = FONT_DIR / "Montserrat-SemiBold.ttf"
FONT_REGULAR = FONT_DIR / "Montserrat-Regular.ttf"

TITLE_FONT_SIZE = 54
SUBTITLE_FONT_SIZE = 26
NAME_FONT_SIZE = 28
META_FONT_SIZE = 20
PCT_FONT_SIZE = 88
SMALL_FONT_SIZE = 18
SEED_FONT_SIZE = 20
FOOTER_FONT_SIZE = 18


# =========================================================
# UTILS
# =========================================================

def load_runtime_config():
    if not RUNTIME_CONFIG_FILE.exists():
        return {}

    with RUNTIME_CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def format_percent_for_post(value):
    value = safe_float(value, 0.0)
    pct = value * 100.0

    if value > 0 and pct < 1:
        return "< 1 %"

    return f"{round(pct):.0f} %"


def build_background(size):
    if BACKGROUND_IMAGE.exists():
        bg = Image.open(BACKGROUND_IMAGE).convert("RGBA")
        bg = fit_cover(bg, size)
    else:
        bg = Image.new("RGBA", size, BACKGROUND_COLOR + (255,))

    if BACKGROUND_OVERLAY is not None:
        overlay = Image.new("RGBA", size, BACKGROUND_OVERLAY)
        bg = Image.alpha_composite(bg, overlay)

    return bg


def ensure_parent_dir(filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def load_font(path, size):
    if Path(path).exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_text_with_shadow(draw, x, y, text, font, fill, shadow_color=(0, 0, 0), shadow_alpha=140):
    draw.text((x + 3, y + 3), text, font=font, fill=shadow_color + (shadow_alpha,))
    draw.text((x + 6, y + 6), text, font=font, fill=shadow_color + (60,))
    draw.text((x, y), text, font=font, fill=fill)


def draw_text_with_glow(draw, x, y, text, font):
    draw.text((x - 1, y - 1), text, font=font, fill=(255, 255, 255, 60))
    draw.text((x + 1, y - 1), text, font=font, fill=(255, 255, 255, 60))
    draw.text((x - 1, y + 1), text, font=font, fill=(255, 255, 255, 60))
    draw.text((x + 1, y + 1), text, font=font, fill=(255, 255, 255, 60))
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 140))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))


def hex_to_rgb(value, default=(68, 68, 68)):
    if value is None:
        return default
    value = str(value).strip().lstrip("#")
    if len(value) != 6:
        return default
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def clamp(value, low=0, high=255):
    return max(low, min(high, int(value)))


def lighten_color(rgb, amount=0.12):
    r, g, b = rgb
    return (
        clamp(r + (255 - r) * amount),
        clamp(g + (255 - g) * amount),
        clamp(b + (255 - b) * amount),
    )


def darken_color(rgb, amount=0.18):
    r, g, b = rgb
    return (
        clamp(r * (1 - amount)),
        clamp(g * (1 - amount)),
        clamp(b * (1 - amount)),
    )


def load_image(path, fallback=None):
    path = Path(path) if path else None
    if path and path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass

    if fallback:
        fallback = Path(fallback)
        if fallback.exists():
            return Image.open(fallback).convert("RGBA")

    return Image.new("RGBA", (100, 100), (80, 80, 80, 255))


def fit_cover(img, size):
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)


def contain_image(img, size):
    img = img.copy()
    img.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - img.width) // 2
    y = (size[1] - img.height) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def crop_circle(img, size):
    img = fit_cover(img, size)
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size[0], size[1]), fill=255)

    result = Image.new("RGBA", size, (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def text_bbox(draw, text, font):
    return draw.textbbox((0, 0), str(text), font=font)


def text_size(draw, text, font):
    bbox = text_bbox(draw, text, font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def truncate_text(draw, text, font, max_width):
    text = str(text)
    if text_size(draw, text, font)[0] <= max_width:
        return text

    ellipsis = "..."
    lo = 0
    hi = len(text)

    while lo < hi:
        mid = (lo + hi) // 2
        candidate = text[:mid].rstrip() + ellipsis
        if text_size(draw, candidate, font)[0] <= max_width:
            lo = mid + 1
        else:
            hi = mid

    return text[: max(0, lo - 1)].rstrip() + ellipsis


def safe_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=None):
    try:
        if pd.isna(value):
            return default
        return int(round(float(value)))
    except Exception:
        return default


def draw_rounded_rectangle(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_vertical_gradient_card(base_img, box, top_color, bottom_color, radius):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1

    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)

    for y in range(h):
        ratio = y / max(1, h - 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        grad_draw.line((0, y, w, y), fill=(r, g, b, 255))

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)

    base_img.paste(gradient, (x1, y1), mask)


# =========================================================
# DATA
# =========================================================

def load_input_dataframe(filepath: Path):
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    df = pd.read_csv(filepath)

    if "player" not in df.columns:
        raise ValueError("Le CSV d'entrée doit contenir une colonne 'player'.")
    if "Top1" not in df.columns:
        raise ValueError("Le CSV d'entrée doit contenir une colonne 'Top1'.")

    sort_cols = ["Top1"]
    ascending = [False]

    if "Top2" in df.columns:
        sort_cols.append("Top2")
        ascending.append(False)

    df = df.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    return df


# =========================================================
# DRAW
# =========================================================

def draw_header(base_img, draw, title_font, subtitle_font, title, subtitle):
    box = (36, 28, WIDTH - 36, 138)
    draw_rounded_rectangle(draw, box, 24, HEADER_COLOR)

    draw.text((58, 46), title, font=title_font, fill=TEXT_COLOR)
    draw.text((58, 103), subtitle, font=subtitle_font, fill=SUBTEXT_COLOR)

    if LOGO_FILE.exists():
        logo = load_image(LOGO_FILE)
        logo = contain_image(logo, (68, 68))
        base_img.paste(logo, (WIDTH - 115, 47), logo)


def draw_footer(draw, footer_font):
    footer = "Source : Elo-Clax"
    w, h = text_size(draw, footer, footer_font)
    draw.text((WIDTH - 36 - w, HEIGHT - 28 - h), footer, font=footer_font, fill=MUTED_TEXT_COLOR)


def draw_seed_badge(draw, seed, x, y, font):
    badge_w = 66
    badge_h = 36
    draw_rounded_rectangle(draw, (x, y, x + badge_w, y + badge_h), 14, fill=(255, 255, 255))
    txt = f"{seed}e"
    tw, th = text_size(draw, txt, font)
    draw.text((x + (badge_w - tw) / 2, y + (badge_h - th) / 2 - 1), txt, font=font, fill=(20, 20, 20))


def draw_player_card(base_img, draw, row, rank, y, fonts):
    name_font = fonts["name"]
    meta_font = fonts["meta"]
    pct_font = fonts["pct"]
    small_font = fonts["small"]
    seed_font = fonts["seed"]

    x = CARD_X
    w = CARD_W
    h = CARD_H

    theme_color = hex_to_rgb(row.get("theme_color", "#444444"))
    top_color = lighten_color(theme_color, 0.10)
    bottom_color = darken_color(theme_color, 0.18)

    draw_vertical_gradient_card(base_img, (x, y, x + w, y + h), top_color, bottom_color, CARD_RADIUS)

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=CARD_RADIUS,
        outline=(255, 255, 255, 36),
        width=2
    )
    base_img.alpha_composite(overlay)

    photo_path = row.get("photo", str(DEFAULT_PHOTO))
    photo = load_image(photo_path, fallback=DEFAULT_PHOTO)
    photo = crop_circle(photo, (PHOTO_SIZE, PHOTO_SIZE))
    base_img.paste(photo, (x + 16, y + 17), photo)

    display_name = clean_text(row.get("display_name", row.get("player", "Joueur")))
    club = clean_text(row.get("club", ""))

    if club:
        full_text = f"{display_name} • {club}"
    else:
        full_text = display_name

    draw_text_with_shadow(draw, x + 124, y + 10, full_text, font=name_font, fill=TEXT_COLOR)

    seed = safe_int(row.get("seed"), default="?")
    draw_seed_badge(draw, seed, x + 124, y + 50, seed_font)

    elo = safe_int(row.get("elo"), default=None)
    top2 = safe_float(row.get("Top2"), default=None)
    top4 = safe_float(row.get("Top4"), default=None)

    meta_parts = []
    if elo is not None:
        meta_parts.append(f"Elo {elo}")
    if top2 is not None and top2 < 0.999:
        meta_parts.append(f"Finale {round(top2 * 100):.0f}%")
    if top4 is not None and top4 < 0.999:
        meta_parts.append(f"Top 4 {round(top4 * 100):.0f}%")

    draw.text((x + 124, y + 93), " • ".join(meta_parts), font=meta_font, fill=SUBTEXT_COLOR)

    top1 = safe_float(row.get("Top1"), default=0.0)
    pct_text = format_percent_for_post(top1)
    pct_x = x + w - 230
    pct_y = y
    draw_text_with_glow(draw, pct_x, pct_y, pct_text, font=pct_font)

    #draw.text((pct_x + 8, y + 88), "chance de titre", font=small_font, fill=SUBTEXT_COLOR)


def main():
    df = load_input_dataframe(INPUT_FILE)

    runtime_config = load_runtime_config()

    title = runtime_config.get("post_title", DEFAULT_TITLE)
    subtitle = runtime_config.get("post_subtitle", DEFAULT_SUBTITLE)

    start_idx = START_RANK - 1
    end_idx = start_idx + TOP_N
    df = df.iloc[start_idx:end_idx].reset_index(drop=True)

    ensure_parent_dir(OUTPUT_FILE)

    title_font = load_font(FONT_TITLE, TITLE_FONT_SIZE)
    subtitle_font = load_font(FONT_SEMIBOLD, SUBTITLE_FONT_SIZE)
    name_font = load_font(FONT_BOLD, NAME_FONT_SIZE)
    meta_font = load_font(FONT_REGULAR, META_FONT_SIZE)
    pct_font = load_font(FONT_PERCENT, PCT_FONT_SIZE)
    small_font = load_font(FONT_REGULAR, SMALL_FONT_SIZE)
    seed_font = load_font(FONT_SEMIBOLD, SEED_FONT_SIZE)
    footer_font = load_font(FONT_REGULAR, FOOTER_FONT_SIZE)

    fonts = {
        "name": name_font,
        "meta": meta_font,
        "pct": pct_font,
        "small": small_font,
        "seed": seed_font,
    }

    img = build_background((WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    draw_header(img, draw, title_font, subtitle_font, title, subtitle)

    for idx, row in df.iterrows():
        y = CARDS_START_Y + idx * (CARD_H + CARD_GAP)
        draw_player_card(img, draw, row, START_RANK + idx, y, fonts)

    draw_footer(draw, footer_font)

    img = img.convert("RGB")
    img.save(OUTPUT_FILE, quality=95)
    print(f"OK : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
    