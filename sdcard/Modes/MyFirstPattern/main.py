import pygame

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    eyesy.color_picker_bg(eyesy.knob5)
    color = eyesy.color_picker(eyesy.knob4)
    r = int(eyesy.knob1 * eyesy.yres / 2)
    pygame.draw.circle(screen, color, (eyesy.xres // 2, eyesy.yres // 2), r)
