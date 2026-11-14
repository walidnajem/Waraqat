"""Material Design 3 design tokens shared by Waraqat's UI.

Every colour is a ``(light, dark)`` tuple so CustomTkinter can switch
appearance modes without rebuilding widgets.
"""

import math
import time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageColor, ImageDraw, ImageTk

# ---------------------------------------------------------------------------
# Colour roles (Material 3 baseline, seeded with Waraqat's indigo brand)
# ---------------------------------------------------------------------------
COLORS = {
    # Primary
    "primary": ("#4F46E5", "#C0C1FF"),
    "on_primary": ("#FFFFFF", "#1B1464"),
    "primary_container": ("#E0E7FF", "#2F2A75"),
    "on_primary_container": ("#1E1B4B", "#E0E0FF"),
    "primary_hover": ("#4338CA", "#D6D7FF"),
    # Secondary
    "secondary": ("#575992", "#C5C4DD"),
    "on_secondary": ("#FFFFFF", "#2A293F"),
    "secondary_container": ("#E8E7FF", "#3F3E57"),
    "on_secondary_container": ("#1B1B3A", "#E4E1F9"),
    "secondary_hover": ("#DAD8FF", "#4E4D68"),
    # Tertiary
    "tertiary": ("#006A60", "#7DD8D0"),
    "on_tertiary": ("#FFFFFF", "#003731"),
    "tertiary_container": ("#B2F2E9", "#00504B"),
    "on_tertiary_container": ("#00201C", "#9CF2E8"),
    # Surfaces
    "surface": ("#FBF8FF", "#131318"),
    "surface_dim": ("#DCD9E0", "#131318"),
    "surface_bright": ("#FBF8FF", "#3A383F"),
    "surface_container_lowest": ("#FFFFFF", "#0E0E13"),
    "surface_container_low": ("#F5F2FA", "#1B1B21"),
    "surface_container": ("#EFEDF4", "#1F1F25"),
    "surface_container_high": ("#E9E7EF", "#292930"),
    "surface_container_highest": ("#E3E1E9", "#34343B"),
    "on_surface": ("#1B1B21", "#E5E1E9"),
    "on_surface_variant": ("#46464F", "#C7C5D0"),
    "outline": ("#777680", "#918F9A"),
    "outline_variant": ("#C7C5D0", "#46464F"),
    "inverse_surface": ("#303038", "#E5E1E9"),
    "inverse_on_surface": ("#F3EFF7", "#303038"),
    # Error
    "error": ("#BA1A1A", "#FFB4AB"),
    "on_error": ("#FFFFFF", "#690005"),
    "error_container": ("#FFDAD6", "#93000A"),
    "on_error_container": ("#410002", "#FFDAD6"),
    "error_hover": ("#FFC7C2", "#B3261E"),
    # Success (application-specific)
    "success": ("#146C2E", "#7ADFA0"),
    "on_success": ("#FFFFFF", "#00390E"),
    "success_container": ("#C4F5C9", "#0A3D1E"),
    "on_success_container": ("#00210A", "#C4F5C9"),
    "success_hover": ("#0F5A25", "#8FF0B0"),
    # Warning (application-specific)
    "warning": ("#8A5300", "#FFB95C"),
    "warning_container": ("#FFDDB3", "#6A3B00"),
    "on_warning_container": ("#2C1700", "#FFDDB3"),
}

# ---------------------------------------------------------------------------
# Shape scale
# ---------------------------------------------------------------------------
RADIUS = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "pill": 20,
}

# ---------------------------------------------------------------------------
# Typography (Segoe UI ships with Windows and renders Arabic well)
# ---------------------------------------------------------------------------
def font(size, weight="normal"):
    """Returns a CustomTkinter-compatible font tuple."""
    if weight and weight != "normal":
        return ("Segoe UI", size, weight)
    return ("Segoe UI", size)


def icon_button_style():
    """Shared style for round icon-only top-app-bar buttons."""
    return {
        "width": 40,
        "height": 40,
        "corner_radius": 20,
        "fg_color": "transparent",
        "hover_color": COLORS["surface_container_high"],
        "text_color": COLORS["on_surface_variant"],
        "border_width": 0,
    }


def center_on_parent(window, parent, width, height):
    """Centers a dialog over its parent, clamped to the visible screen.

    Keeps buttons reachable when the main window sits low on the desktop or
    when the dialog is nearly as tall as the work area.
    """
    window.update_idletasks()
    try:
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        x = px + (pw - width) // 2
        y = py + (ph - height) // 2

        max_x = window.winfo_screenwidth() - width - 20
        max_y = window.winfo_screenheight() - height - 60  # leave room for taskbar
        x = max(20, min(x, max_x))
        y = max(20, min(y, max_y))
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Material 3 Expressive components
# ---------------------------------------------------------------------------
def _resolve(color):
    """Resolves a ``(light, dark)`` tuple to the active appearance colour."""
    if isinstance(color, tuple):
        light, dark = color
        return light if ctk.get_appearance_mode().lower() == "light" else dark
    return color


def _rgb(color):
    """Converts a named/hex colour (or a light/dark tuple) to RGB."""
    try:
        return ImageColor.getrgb(_resolve(color))[:3]
    except Exception:
        return (128, 128, 128)


class WavyProgressBar(tk.Canvas):
    """Material 3 Expressive wavy linear progress indicator.

    Idle (before a download starts) the bar is a calm, flat track. Calling
    :meth:`start` switches it to a soft sine wave that travels along the
    bar for as long as the download is running; :meth:`stop` returns it to
    a static line.

    The bar is rendered with PIL at a higher resolution and downsampled
    with Lanczos, so curves and rounded caps stay smooth instead of the
    aliased, stair-stepped lines native Tk canvases produce.
    """

    def __init__(
        self,
        master,
        height=14,
        value=0.0,
        progress_color=("#4F46E5", "#C0C1FF"),
        track_color=("#C7C5D0", "#46464F"),
        surface_color=("#FBF8FF", "#131318"),
        amplitude=2.6,
        wavelength=38,
        thickness=4.5,
        animation_interval=45,
        speed=42.0,
        **kwargs,
    ):
        self._value = max(0.0, min(1.0, float(value)))
        self._display_value = self._value
        self._progress_color = progress_color
        self._track_color = track_color
        self._surface_color = surface_color
        self._amplitude = amplitude
        self._wavelength = max(16, wavelength)
        self._thickness = thickness
        self._animated = False
        self._phase = 0.0
        self._anim_job = None
        self._anim_interval = max(20, int(animation_interval))
        self._speed = max(1.0, float(speed))
        self._last_tick = time.monotonic()
        self._photo = None
        self._img_id = None
        self._asset_key = None
        self._track_strip = None
        self._fill_strip = None
        self._track_cap = None
        self._fill_cap = None

        super().__init__(
            master,
            height=height,
            bg=_resolve(surface_color),
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Destroy>", self._on_destroy)
        self.after_idle(self._redraw)

    # -- public API --------------------------------------------------------
    def set(self, value):
        """Sets progress between 0.0 and 1.0."""
        self._value = max(0.0, min(1.0, float(value)))
        if not self._animated:
            # Static bars update instantly; animated bars glide towards the
            # new target on the next frame instead of jumping.
            self._display_value = self._value
            self._redraw()

    def get(self):
        return self._value

    def start(self):
        """Begins the travelling wave animation (idempotent)."""
        if self._animated:
            return
        self._animated = True
        self._phase = 0.0
        self._last_tick = time.monotonic()
        self._tick()

    def stop(self):
        """Stops the animation and returns to a calm, static bar."""
        self._animated = False
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
        self._display_value = self._value
        self._redraw()

    def is_animating(self):
        return self._animated

    def set_colors(self, progress_color=None, track_color=None, surface_color=None):
        """Updates one or more colour tuples without rebuilding the widget."""
        changed = False
        if progress_color is not None and progress_color != self._progress_color:
            self._progress_color = progress_color
            changed = True
        if track_color is not None and track_color != self._track_color:
            self._track_color = track_color
            changed = True
        if surface_color is not None and surface_color != self._surface_color:
            self._surface_color = surface_color
            changed = True
            try:
                self.configure(bg=_resolve(surface_color))
            except Exception:
                pass
        if changed:
            self._redraw()

    def set_surface(self, surface_color):
        """Matches the canvas background to its parent container."""
        if surface_color == self._surface_color:
            return
        self._surface_color = surface_color
        try:
            self.configure(bg=_resolve(surface_color))
        except Exception:
            pass
        self._redraw()

    def refresh_theme(self):
        """Re-resolves theme-aware colours after an appearance switch."""
        try:
            self.configure(bg=_resolve(self._surface_color))
        except Exception:
            pass
        self._redraw()

    # -- animation ---------------------------------------------------------
    def _tick(self):
        self._anim_job = None
        if not self._animated:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        # Guard against a stalled event loop producing a sudden jump.
        if dt <= 0 or dt > 0.25:
            dt = self._anim_interval / 1000.0

        self._phase = (
            self._phase + math.tau * self._speed * dt / self._wavelength
        ) % math.tau

        gap = self._value - self._display_value
        if abs(gap) < 0.001:
            self._display_value = self._value
        else:
            # Exponential easing: the fill glides instead of stepping.
            self._display_value += gap * (1.0 - math.exp(-dt * 14.0))

        self._redraw()
        try:
            self._anim_job = self.after(self._anim_interval, self._tick)
        except Exception:
            self._anim_job = None

    def _on_destroy(self, _event=None):
        self._animated = False
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    # -- drawing -----------------------------------------------------------
    def _redraw(self):
        try:
            width = int(self.winfo_width())
            height = int(self.winfo_height())
            if width <= 2 or height <= 2:
                return

            if self._animated:
                image = self._render_animated(width, height)
            else:
                image = self._render_static(width, height)
            if image is None:
                return

            photo = ImageTk.PhotoImage(image, master=self)
            if not self._img_id or not self.type(self._img_id):
                self.delete("wave")
                self._img_id = self.create_image(
                    0, 0, anchor="nw", image=photo, tags="wave"
                )
            else:
                self.itemconfigure(self._img_id, image=photo)
            self._photo = photo
        except Exception:
            pass

    # -- rendering helpers -------------------------------------------------
    def _assets(self, width, height, scale):
        """Pre-renders scrolling waves and round caps at full resolution.

        The expensive anti-aliased drawing happens only when geometry or
        colours change; each animation frame then just crops and scrolls
        the cached strips, which keeps the motion smooth and cheap.
        """
        progress_rgb = _rgb(self._progress_color)
        track_rgb = _rgb(self._track_color)
        surface_rgb = _rgb(self._surface_color)
        key = (
            width,
            height,
            scale,
            progress_rgb,
            track_rgb,
            surface_rgb,
            round(self._amplitude, 2),
            round(self._wavelength, 2),
            round(self._thickness, 2),
        )
        if key == self._asset_key:
            return

        margin = int(math.ceil(self._wavelength)) + 4
        strip_width = width + 2 * margin
        self._track_strip = self._render_wave_strip(
            strip_width, height, scale, track_rgb, surface_rgb
        )
        self._fill_strip = self._render_wave_strip(
            strip_width, height, scale, progress_rgb, surface_rgb
        )
        self._track_cap = self._render_cap(scale, track_rgb)
        self._fill_cap = self._render_cap(scale, progress_rgb)
        self._asset_key = key

    def _render_wave_strip(self, width, height, scale, color, surface):
        image = Image.new(
            "RGB", (width * scale, height * scale), surface
        )
        drawer = ImageDraw.Draw(image)
        center = (height / 2.0) * scale
        thickness = max(2, int(round(self._thickness * scale)))
        amplitude = max(
            0.0,
            min(self._amplitude, (height - self._thickness) / 2.0 - 1.0),
        ) * scale
        wavelength = self._wavelength * scale

        # Draw a continuous band between the upper and lower wave edges.
        # Filling one polygon avoids the costly per-joint circles PIL uses
        # for thick polylines, while still giving perfectly round curves.
        top = []
        bottom = []
        x = 0
        step = max(1, scale)
        while x <= width * scale:
            y = center + amplitude * math.sin(math.tau * x / wavelength)
            top.append((x, y - thickness / 2.0))
            bottom.append((x, y + thickness / 2.0))
            x += step
        if top:
            drawer.polygon(top + bottom[::-1], fill=color)
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def _render_cap(self, scale, color):
        """Anti-aliased round cap sprite for one end of a wave."""
        tile = max(3, int(math.ceil(self._thickness)) + 2)
        big = tile * scale
        image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        drawer = ImageDraw.Draw(image)
        offset = (tile - self._thickness) / 2.0 * scale
        drawer.ellipse(
            (offset, offset, big - offset, big - offset),
            fill=color + (255,),
        )
        return image.resize((tile, tile), Image.Resampling.LANCZOS)

    @staticmethod
    def _paste_cap(image, cap, x, y):
        if cap is None:
            return
        px = int(round(x - cap.width / 2.0))
        py = int(round(y - cap.height / 2.0))
        image.paste(cap, (px, py), cap)

    def _render_animated(self, width, height):
        scale = 4 if width <= 620 else 3
        self._assets(width, height, scale)
        if self._track_strip is None:
            return None

        wavelength = max(1, int(round(self._wavelength)))
        margin = int(math.ceil(self._wavelength)) + 4
        offset = int(round((self._phase % math.tau) / math.tau * wavelength))
        offset = min(max(0, offset), wavelength - 1)
        origin = margin + offset

        # Scroll the pre-rendered track by cropping a moving window.
        image = self._track_strip.crop(
            (origin, 0, origin + width, height)
        ).copy()

        radius = self._thickness / 2.0
        left = radius
        right = width - radius
        center = height / 2.0
        amplitude = max(
            0.0,
            min(self._amplitude, (height - self._thickness) / 2.0 - 1.0),
        )

        def wave_y(x):
            return center + amplitude * math.sin(
                math.tau * (origin + x) / self._wavelength
            )

        # Round the two ends of the track pill.
        self._paste_cap(image, self._track_cap, left, wave_y(left))
        self._paste_cap(image, self._track_cap, right, wave_y(right))

        fill_px = width * self._display_value
        if fill_px > 0.5:
            end = min(right, max(left, fill_px - radius))
            if end > left + 1.0:
                # Crop the fill wave to the filled width and paste it over
                # the track; both strips share the exact same phase.
                start_x = origin + int(round(left))
                end_x = origin + int(round(end))
                piece = self._fill_strip.crop(
                    (start_x, 0, end_x, height)
                )
                image.paste(piece, (int(round(left)), 0))
                self._paste_cap(image, self._fill_cap, left, wave_y(left))
                self._paste_cap(image, self._fill_cap, end, wave_y(end))
            else:
                self._paste_cap(image, self._fill_cap, left, wave_y(left))
        return image

    def _render_static(self, width, height):
        scale = 4 if width <= 620 else 3
        surface = _rgb(self._surface_color)
        image = Image.new("RGB", (width * scale, height * scale), surface)
        drawer = ImageDraw.Draw(image)
        center = (height / 2.0) * scale
        thickness = max(2, int(round(self._thickness * scale)))
        radius = thickness / 2.0
        left = radius
        right = width * scale - radius
        if right <= left:
            return None

        def draw_pill(x_end, color):
            x_start = left
            x_stop = max(x_start + radius, x_end)
            drawer.rounded_rectangle(
                (x_start, center - radius, x_stop, center + radius),
                radius=radius,
                fill=color,
            )

        draw_pill(right, _rgb(self._track_color))
        fill_end = left + (right - left) * self._display_value
        if self._display_value > 0.0:
            draw_pill(fill_end, _rgb(self._progress_color))
        return image.resize((width, height), Image.Resampling.LANCZOS)
