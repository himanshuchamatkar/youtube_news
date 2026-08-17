import os
import random
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

class ChartGenerator:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.primary_color = (13, 27, 42)    # Dark Navy
        self.accent_color = (241, 196, 15)    # Gold
        self.success_color = (46, 204, 113)  # Green
        self.danger_color = (231, 76, 60)    # Red
        self.text_color = (248, 249, 250)    # Off-White

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        # Load a default true-type font. On Windows, Arial is standard.
        # Fall back to default if not found.
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def generate_headline_card(self, headline: str, company: str, sector: str, output_path: str):
        # Create a transparent overlay card (size: 960x270) to place near the top
        card_w, card_h = 960, 270
        img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle background (glassmorphism look: semi-transparent navy)
        draw.rounded_rectangle(
            [(10, 10), (card_w - 10, card_h - 10)],
            radius=20,
            fill=(10, 25, 47, 220), # Semi-transparent dark navy
            outline=(241, 196, 15, 255), # Gold outline
            width=3
        )

        # Draw Headline
        font_title = self._get_font(34)
        font_tag = self._get_font(20)

        # Wrap headline text if long
        wrapped_lines = []
        words = headline.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) > 42:
                wrapped_lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            wrapped_lines.append(current_line)

        # Draw wrapped lines
        y_text = 35
        for line in wrapped_lines[:2]: # Limit to 2 lines for compactness
            draw.text((40, y_text), line, font=font_title, fill=self.text_color)
            y_text += 45

        # Draw Company Tag and Sector Badge
        y_tag = card_h - 75
        if company and company != "N/A":
            # Draw tag box
            draw.rounded_rectangle(
                [(40, y_tag), (350, y_tag + 40)],
                radius=8,
                fill=(46, 204, 113, 200) # Green background
            )
            draw.text((55, y_tag + 8), company[:20], font=font_tag, fill=(255, 255, 255))
            
        if sector and sector != "N/A":
            draw.rounded_rectangle(
                [(380, y_tag), (680, y_tag + 40)],
                radius=8,
                fill=(52, 152, 219, 200) # Blue background
            )
            draw.text((395, y_tag + 8), sector[:18], font=font_tag, fill=(255, 255, 255))

        # Save card
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"ChartGenerator: Created headline card at {output_path}")

    def generate_stock_chart(self, company_name: str, score: int, output_path: str):
        # Generate an animated stock line chart using Matplotlib and save as MP4
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        
        # Force chart file extension to mp4
        output_path = output_path.replace(".png", ".mp4")
        
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
        
        # Style chart (match dark premium layout)
        fig.patch.set_facecolor('#112240')
        ax.set_facecolor('#112240')
        
        # Mock stock price trend
        random.seed(score)
        prices = [100.0]
        for _ in range(30):
            change = random.uniform(-0.02, 0.035)
            prices.append(prices[-1] * (1 + change))
            
        x_data = list(range(len(prices)))
        y_data = prices
        
        # Color based on trend
        is_positive = y_data[-1] > y_data[0]
        line_color = '#2ecc71' if is_positive else '#e74c3c'
        fill_color = '#2ecc71' if is_positive else '#e74c3c'
        
        # Set chart limits
        ax.set_xlim(0, len(prices) - 1)
        ax.set_ylim(min(y_data) * 0.98, max(y_data) * 1.02)
        
        # Labels and grid
        ax.set_title(f"{company_name} - Performance", color='#f8f9fa', fontsize=10, fontweight='bold', pad=10)
        ax.tick_params(colors='#8892b0', labelsize=8)
        ax.grid(True, linestyle='--', alpha=0.1, color='#8892b0')
        for spine in ax.spines.values():
            spine.set_color('#243b55')
            
        line, = ax.plot([], [], color=line_color, linewidth=2.5)
        fill = [None]
        
        def init():
            line.set_data([], [])
            return line,
            
        def update(frame):
            # Total frames: 15 seconds * 30 fps = 450 frames
            # Drawing phase: first 120 frames (4 seconds)
            step = min(frame // 4, 30)
            
            x_curr = x_data[:step + 1]
            y_curr = y_data[:step + 1]
            line.set_data(x_curr, y_curr)
            
            # Remove old fill
            if fill[0] is not None:
                fill[0].remove()
            # Draw new fill
            if len(x_curr) > 1:
                fill[0] = ax.fill_between(x_curr, min(y_data)*0.96, y_curr, color=fill_color, alpha=0.15)
                
            return line,
            
        ani = animation.FuncAnimation(fig, update, frames=450, init_func=init, blit=True)
        
        # Save as MP4 using ffmpeg writer
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        writer = animation.FFMpegWriter(fps=30, metadata=dict(artist='ShortsFactory'), bitrate=1800)
        ani.save(output_path, writer=writer)
        plt.close(fig)
        print(f"ChartGenerator: Generated animated chart video at {output_path}")
        
    def generate_percentage_badge(self, movement: float, output_path: str):
        # Create a percentage change badge (e.g. +5.2%)
        card_w, card_h = 320, 160
        img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        is_positive = movement >= 0
        fill_color = self.success_color if is_positive else self.danger_color
        text_val = f"+{movement:.2f}%" if is_positive else f"{movement:.2f}%"
        
        draw.rounded_rectangle(
            [(5, 5), (card_w - 5, card_h - 5)],
            radius=15,
            fill=(*fill_color, 230),
            outline=(255, 255, 255, 255),
            width=2
        )
        
        font_pct = self._get_font(48)
        font_sub = self._get_font(20)
        
        # Text alignment
        draw.text((35, 20), text_val, font=font_pct, fill=(255, 255, 255))
        draw.text((35, 95), "MARKET CHANGE" if is_positive else "MARKET CHANGE", font=font_sub, fill=(255, 255, 255))
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"ChartGenerator: Created percentage badge at {output_path}")
