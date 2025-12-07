class Camera:
    def __init__(self, room_width_px, room_height_px, screen_w, screen_h):
        self.room_w = room_width_px
        self.room_h = room_height_px
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.offset_x = 0
        self.offset_y = 0

    def update(self, target_rect, room_origin_x=0, room_origin_y=0):
        new_x = target_rect.centerx - self.screen_w // 2
        new_y = target_rect.centery - self.screen_h // 2

        if self.room_w > self.screen_w:
            self.offset_x = max(room_origin_x, min(new_x, room_origin_x + self.room_w - self.screen_w))
        else:
            self.offset_x = room_origin_x - (self.screen_w - self.room_w) // 2

        if self.room_h > self.screen_h:
            self.offset_y = max(room_origin_y, min(new_y, room_origin_y + self.room_h - self.screen_h))
        else:
            self.offset_y = room_origin_y - (self.screen_h - self.room_h) // 2

    def apply(self, world_rect):
        return world_rect.move(-self.offset_x, -self.offset_y)