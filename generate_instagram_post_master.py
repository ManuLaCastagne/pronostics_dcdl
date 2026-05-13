from pathlib import Path
import math
import json
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = "outputs/csv/master_post_ready.csv"
#INPUT_FILE = "outputs/csv/pronostic_elo_post_ready.csv"
OUTPUT_FILE = "outputs/images/instagram_top5_master.png"

RUNTIME_CONFIG_FILE = BASE_DIR / "data" / "runtime_config.json"

WIDTH = 1080
HEIGHT = 1350

TOP_N = 5
START_RANK = 1

DEFAULT_TITLE = "Probabilité de victoire"
DEFAULT_SUBTITLE = ""

BACKGROUND_COLOR = (16, 18, 24)
HEADER_BOX_COLOR = (28, 32, 42)
TEXT_COLOR = (255, 255, 255)
SUBTEXT_COLOR = (220, 224, 230)
MUTED_TEXT_COLOR = (190, 196, 205)
RANK_BOX_TEXT_COLOR = (20, 20, 20)
RANK_BOX_FILL = (255, 255, 255)

CARD_X = 40
CARD_WIDTH = WIDTH - 80
CARD_HEIGHT = 205
CARD_RADIUS = 28
CARD_GAP = 18
CARDS_START_Y = 190

PHOTO_SIZE = 172
PHOTO_MARGIN_LEFT = 22
PHOTO_MARGIN_TOP = 17

DEFAULT_PHOTO = "assets/players/default.png"
DEFAULT_FLAG = "assets/flags/default.png"
DEFAULT_CLUB = "assets/clubs/default.png"
DEFAULT_BACKGROUND = "assets/backgrounds/plateau.png"

LOGO_FILE = "assets/icons/default.png"
TROPHY_FILE = "assets/icons/trophy.png"

SHOW_FLAG = False
SHOW_CLUB_LOGO = True
SHOW_TROPHY = True

FONT_DIR = "assets/fonts/"

FONT_PERCENT = FONT_DIR + "Anton-Regular.ttf"
FONT_TITLE = FONT_DIR + "Montserrat-ExtraBoldItalic.ttf"
FONT_BOLD = FONT_DIR + "Montserrat-Bold.ttf"
FONT_SEMIBOLD = FONT_DIR + "Montserrat-SemiBold.ttf"
FONT_REGULAR = FONT_DIR + "Montserrat-Regular.ttf"

FONT_BOLD_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
]
FONT_REGULAR_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]

TITLE_FONT_SIZE = 50
SUBTITLE_FONT_SIZE = 28
NAME_FONT_SIZE = 40
META_FONT_SIZE = 35
PCT_FONT_SIZE = 100
PERCENT_LABEL_FONT_SIZE = 25
RANK_FONT_SIZE = 25
SMALL_FONT_SIZE = 20
SEED_FONT_SIZE = 22
FOOTER_FONT_SIZE = 18


# =========================================================
# UTILS
# =========================================================

def load_runtime_config():
    if not RUNTIME_CONFIG_FILE.exists():
        return {}

    with RUNTIME_CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def draw_text_with_shadow(draw, x, y, text, font, fill, shadow_color=(0,0,0), shadow_alpha=140):
    # ombre principale
    draw.text((x + 3, y + 3), text, font=font, fill=shadow_color + (shadow_alpha,))

    # légère deuxième ombre (plus diffuse)
    draw.text((x + 6, y + 6), text, font=font, fill=shadow_color + (60,))

    # texte principal
    draw.text((x, y), text, font=font, fill=fill)

def draw_text_with_glow(draw, x, y, text, font):
    # glow léger
    draw.text((x - 1, y - 1), text, font=font, fill=(255,255,255,60))
    draw.text((x + 1, y - 1), text, font=font, fill=(255,255,255,60))
    draw.text((x - 1, y + 1), text, font=font, fill=(255,255,255,60))
    draw.text((x + 1, y + 1), text, font=font, fill=(255,255,255,60))

    # ombre
    draw.text((x + 3, y + 3), text, font=font, fill=(0,0,0,140))

    # texte
    draw.text((x, y), text, font=font, fill=(255,255,255))

def format_percent_for_post(value):
    value = safe_float(value, 0.0)
    pct = value * 100.0

    if value > 0 and pct < 1:
        return "< 1 %"

    return f"{round(pct):.0f} %"

def ensure_parent_dir(filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

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


def lighten_color(rgb, amount=0.18):
    r, g, b = rgb
    return (
        clamp(r + (255 - r) * amount),
        clamp(g + (255 - g) * amount),
        clamp(b + (255 - b) * amount),
    )


def darken_color(rgb, amount=0.20):
    r, g, b = rgb
    return (
        clamp(r * (1 - amount)),
        clamp(g * (1 - amount)),
        clamp(b * (1 - amount)),
    )


def load_image(path, fallback=None):
    if path and Path(path).exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass

    if fallback and Path(fallback).exists():
        return Image.open(fallback).convert("RGBA")

    # image vide de secours
    return Image.new("RGBA", (200, 200), (90, 90, 90, 255))


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


def paste_with_alpha(base_img, overlay_img, x, y):
    base_img.paste(overlay_img, (x, y), overlay_img)


def text_bbox(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)


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

    final = text[: max(0, lo - 1)].rstrip() + ellipsis
    return final


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


def add_soft_glow(base_img, center_x, center_y, radius, color=(255, 255, 255), alpha=70):
    glow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    steps = 10
    for i in range(steps, 0, -1):
        rr = int(radius * i / steps)
        a = int(alpha * (i / steps) ** 2 / 2)
        glow_draw.ellipse(
            (center_x - rr, center_y - rr, center_x + rr, center_y + rr),
            fill=(color[0], color[1], color[2], a)
        )

    base_img.alpha_composite(glow)


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


# =========================================================
# DATA PREP
# =========================================================

def load_input_dataframe(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    df = pd.read_csv(path)

    if "player" not in df.columns:
        raise ValueError("Le CSV d'entrée doit contenir une colonne 'player'.")
    if "Top1" not in df.columns:
        raise ValueError("Le CSV d'entrée doit contenir une colonne 'Top1'.")

    sort_cols = ["Top1"]
    ascending = [False]

    if "expected_points" in df.columns:
        sort_cols.append("expected_points")
        ascending.append(False)
    elif "sim_expected_points" in df.columns:
        sort_cols.append("sim_expected_points")
        ascending.append(False)

    df = df.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    return df


# =========================================================
# DRAWING HELPERS
# =========================================================

def draw_header(base_img, draw, title_font, subtitle_font, title, subtitle):
    header_box = (40, 30, WIDTH - 40, 145)
    draw_rounded_rectangle(draw, header_box, radius=26, fill=HEADER_BOX_COLOR)

    title_x = 60
    title_y = 48
    subtitle_x = 60
    subtitle_y = 103

    draw.text((title_x, title_y), title, font=title_font, fill=TEXT_COLOR)
    draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=SUBTEXT_COLOR)

    if Path(LOGO_FILE).exists():
        logo = load_image(LOGO_FILE)
        logo = contain_image(logo, (72, 72))
        paste_with_alpha(base_img, logo, WIDTH - 125, 52)


def draw_footer(draw, footer_font):
    footer_text = "Source : Elo-Clax"
    w, h = text_size(draw, footer_text, footer_font)
    x = WIDTH - 45 - w
    y = HEIGHT - 35 - h
    draw.text((x, y), footer_text, font=footer_font, fill=MUTED_TEXT_COLOR)


def draw_rank_box(draw, rank, x_right, y_top, font):
    box_w = 78
    box_h = 54
    x1 = x_right - box_w
    y1 = y_top
    x2 = x_right
    y2 = y_top + box_h

    draw_rounded_rectangle(draw, (x1, y1, x2, y2), radius=18, fill=RANK_BOX_FILL)

    rank_text = f"#{rank}"
    tw, th = text_size(draw, rank_text, font)
    tx = x1 + (box_w - tw) / 2
    ty = y1 + (box_h - th) / 2 - 2
    draw.text((tx, ty), rank_text, font=font, fill=RANK_BOX_TEXT_COLOR)


def draw_flag_if_any(base_img, row, x, y):
    if not SHOW_FLAG:
        return 0

    flag_path = row.get("flag", DEFAULT_FLAG)
    if not flag_path:
        return 0

    flag = load_image(flag_path, fallback=DEFAULT_FLAG)
    flag = contain_image(flag, (46, 32))

    bg = Image.new("RGBA", (54, 40), (255, 255, 255, 235))
    bg_mask = Image.new("L", (54, 40), 0)
    ImageDraw.Draw(bg_mask).rounded_rectangle((0, 0, 54, 40), radius=10, fill=255)

    card = Image.new("RGBA", (54, 40), (0, 0, 0, 0))
    card.paste(bg, (0, 0), bg_mask)
    card.paste(flag, ((54 - flag.width) // 2, (40 - flag.height) // 2), flag)

    paste_with_alpha(base_img, card, x, y)
    return 60


def draw_club_logo_if_any(base_img, row, x, y):
    if not SHOW_CLUB_LOGO:
        return 0

    club_path = row.get("club_logo", DEFAULT_CLUB)
    if not club_path:
        return 0

    club = load_image(club_path, fallback=DEFAULT_CLUB)
    club = contain_image(club, (36, 36))
    paste_with_alpha(base_img, club, x, y)
    return 44


def draw_trophy_if_any(base_img, x, y):
    if not SHOW_TROPHY or not Path(TROPHY_FILE).exists():
        return

    trophy = load_image(TROPHY_FILE)
    trophy = contain_image(trophy, (74, 74))
    paste_with_alpha(base_img, trophy, x, y)


def draw_player_card(base_img, draw, row, rank, y, fonts):
    name_font = fonts["name"]
    meta_font = fonts["meta"]
    percent_font = fonts["percent"]
    percent_label_font = fonts["percent_label"]
    rank_font = fonts["rank"]

    x = CARD_X
    w = CARD_WIDTH
    h = CARD_HEIGHT

    theme_color = hex_to_rgb(row.get("theme_color", "#444444"))
    top_color = lighten_color(theme_color, 0.10)
    bottom_color = darken_color(theme_color, 0.18)

    card_box = (x, y, x + w, y + h)
    draw_vertical_gradient_card(base_img, card_box, top_color, bottom_color, CARD_RADIUS)

    # petit reflet
    add_soft_glow(base_img.convert("RGBA"), x + 110, y + 45, 120)

    # séparation douce
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=CARD_RADIUS,
        outline=(255, 255, 255, 40),
        width=2
    )
    base_img.alpha_composite(overlay)

    # photo
    photo_path = row.get("photo", DEFAULT_PHOTO)
    photo = load_image(photo_path, fallback=DEFAULT_PHOTO)
    photo = crop_circle(photo, (PHOTO_SIZE, PHOTO_SIZE))
    paste_with_alpha(base_img, photo, x + PHOTO_MARGIN_LEFT, y + PHOTO_MARGIN_TOP)

    # nom + club
    text_x = x + 220
    name_y = y + 18
    meta_y = y + 62
    club_y = y + 48

    max_width = 360

    display_name = row.get("display_name", row.get("player", "Joueur"))
    club = clean_text(row.get("club", ""))

    if club:
        full_text = f"{display_name} \n{club}"
    else:
        full_text = display_name

    draw_text_with_shadow(draw, x + 210, y + 25, full_text, font=name_font, fill=TEXT_COLOR)

    # elo sous le nom
    elo = safe_float(row.get("elo_effective", row.get("elo", None)))
    if elo is not None:
        elo_text = f"Elo {int(round(elo))}"
        draw_text_with_shadow(draw, x + 210, y + 125, elo_text, font=meta_font, fill=SUBTEXT_COLOR)

    # badges sous le nom
    # badge_y = y + 76
    # current_x = text_x

    # current_x += draw_flag_if_any(base_img, row, current_x, badge_y - 4)
    # current_x += draw_club_logo_if_any(base_img, row, current_x, badge_y - 2)

    # meta ligne 1
    # elo = safe_float(row.get("elo_effective", row.get("elo", None)))
    # points = safe_float(row.get("expected_points", row.get("sim_expected_points", None)))

    # meta_parts = []
    # if elo is not None:
    #     meta_parts.append(f"Elo {int(round(elo))}")
    # if points is not None:
    #     meta_parts.append(f"Pts attendus {points:.1f}")

    # meta_text = " • ".join(meta_parts) if meta_parts else ""
    # if meta_text:
    #     draw.text((text_x, y + 84), meta_text, font=meta_font, fill=SUBTEXT_COLOR)

    # meta ligne 2
    
    # secondary_parts = []
    # top3 = safe_float(row.get("Top<=3", None))
    # top5 = safe_float(row.get("Top<=5", None))
    # if top3 is not None:
    #     secondary_parts.append(f"Top 3 {round(top3 * 100):.0f}%")
    # if top5 is not None:
    #     secondary_parts.append(f"Top 5 {round(top5 * 100):.0f}%")

    # secondary_text = " • ".join(secondary_parts)
    # if secondary_text:
    #     draw.text((text_x, y + 116), secondary_text, font=meta_font, fill=MUTED_TEXT_COLOR)

    # pourcentage principal
    top1 = safe_float(row.get("Top1"), default=0.0)
    pct_text = format_percent_for_post(top1)

    pct_x = x + w - 270
    pct_y = y + 20
    draw_text_with_glow(draw, pct_x, pct_y, pct_text, font=percent_font)

    # rang
    # draw_rank_box(draw, rank, x + w - 18, y + 18, rank_font)

    # trophée optionnel
    # draw_trophy_if_any(base_img, x + w - 115, y + 123)


# =========================================================
# MAIN
# =========================================================

def main():
    runtime_config = load_runtime_config()

    title = runtime_config.get("post_title", DEFAULT_TITLE)
    subtitle = runtime_config.get("post_subtitle", DEFAULT_SUBTITLE)
    
    df = load_input_dataframe(INPUT_FILE)

    start_idx = START_RANK - 1
    end_idx = start_idx + TOP_N

    df = df.iloc[start_idx:end_idx].reset_index(drop=True)

    ensure_parent_dir(OUTPUT_FILE)

    title_font = load_font(FONT_TITLE, TITLE_FONT_SIZE)
    subtitle_font = load_font(FONT_SEMIBOLD, SUBTITLE_FONT_SIZE)

    name_font = load_font(FONT_BOLD, NAME_FONT_SIZE)
    meta_font = load_font(FONT_REGULAR, META_FONT_SIZE)

    pct_font = load_font(FONT_PERCENT, PCT_FONT_SIZE)  # ⭐ le plus important

    small_font = load_font(FONT_REGULAR, SMALL_FONT_SIZE)
    seed_font = load_font(FONT_SEMIBOLD, SEED_FONT_SIZE)
    footer_font = load_font(FONT_REGULAR, FOOTER_FONT_SIZE)

    fonts = {
        "name": name_font,
        "meta": meta_font,
        "percent": pct_font,
        "percent_label": small_font,
        "rank": seed_font,
    }

    if DEFAULT_BACKGROUND and Path(DEFAULT_BACKGROUND).exists():
        bg = load_image(DEFAULT_BACKGROUND).convert("RGB")
        bg = fit_cover(bg, (WIDTH, HEIGHT))
        img = bg.convert("RGBA")
    else:
        img = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND_COLOR + (255,))

    draw = ImageDraw.Draw(img)

    draw_header(img, draw, title_font, subtitle_font, title, subtitle)

    for idx, row in df.iterrows():
        y = CARDS_START_Y + idx * (CARD_HEIGHT + CARD_GAP)
        draw_player_card(img, draw, row, idx + 1, y, fonts)

    draw_footer(draw, footer_font)

    img = img.convert("RGB")
    img.save(OUTPUT_FILE, quality=95)
    print(f"OK : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()