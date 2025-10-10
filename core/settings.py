class Settings:
    def __init__(self):
        # Default: warm orange tint, medium opacity
        self.color = (255, 170, 100)  # RGB
        self.opacity = 0.4            # 0.0–1.0 range

    def set_color(self, color_tuple):
        self.color = color_tuple

    def set_opacity(self, value):
        self.opacity = value
        
