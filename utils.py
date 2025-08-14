def rects_collide(a, b):
    return not (
        a.rect.x + a.rect.width < b.rect.x or
        a.rect.x > b.rect.x + b.rect.width or
        a.rect.y + a.rect.height < b.rect.y or
        a.rect.y > b.rect.y + b.rect.height
    )

def clamp(value, min_value, max_value):
    """限制 value 在 [min_value, max_value] 范围内"""
    return max(min_value, min(value, max_value))
