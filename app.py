import json
import math
import os
import random
import sys

import pygame

pygame.init()

# ============================
# WINDOW SETUP
# ============================
WIDTH, HEIGHT = 1200, 760
PANEL_WIDTH = 240
MAP_WIDTH = WIDTH - PANEL_WIDTH
TOP_BAR = 60
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tiny City Builder")
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 18)
small_font = pygame.font.SysFont("arial", 14)
big_font = pygame.font.SysFont("arial", 24)

# ============================
# COLORS
# ============================
GRASS = (199, 232, 181)
DOT = (166, 184, 156)
ROAD_DARK = (85, 89, 94)
ROAD_LIGHT = (226, 226, 216)
PANEL = (38, 44, 52)
TOP = (43, 50, 58)
WHITE = (250, 250, 245)
BLACK = (17, 21, 26)
YELLOW = (255, 212, 87)
GREEN = (82, 182, 93)
RED = (230, 90, 72)
BLUE = (98, 142, 236)
PINK = (221, 160, 242)

# ============================
# GAME STATE
# ============================
money = 350
roads = []
buildings = []
vehicles = []
selected_tool = "Road"
selected_object = None

drawing_road = None
last_road_point = None
dragging_building = None

message = ""
message_timer = 0
car_timer = 0
income_timer = 0
SAVE_FILE = "city_save.json"

# ============================
# HELPERS
# ============================
def draw_text(text, x, y, color=WHITE, f=font):
    image = f.render(str(text), True, color)
    screen.blit(image, (int(x), int(y)))


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def inside_map(pos):
    x, y = pos
    return 0 <= x < MAP_WIDTH and TOP_BAR <= y < HEIGHT


def snap_point(pos):
    x, y = pos
    x = max(0, min(MAP_WIDTH, x))
    y = max(TOP_BAR, min(HEIGHT, y))
    return (round(x / 20) * 20, round(y / 20) * 20)


def nearest_point_on_segment(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return a
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0, min(1, t))
    return (ax + t * dx, ay + t * dy)


def building_at(pos):
    for building in reversed(buildings):
        if distance(pos, (building["x"], building["y"])) < 24:
            return building
    return None


def road_at(pos, max_distance=18):
    for road in reversed(roads):
        points = road["points"]
        for i in range(len(points) - 1):
            nearest = nearest_point_on_segment(pos, points[i], points[i + 1])
            if distance(pos, nearest) < max_distance:
                return road
    return None


def show_message(text):
    global message, message_timer
    message = text
    message_timer = 2.5


def get_building_cost(kind):
    return {
        "House": 80,
        "Hospital": 180,
        "Fuel Station": 150,
        "Bridge": 220,
    }.get(kind, 100)


def get_upgrade_cost(item):
    if "points" in item:
        return item["level"] * 60
    return item["level"] * 80


def maybe_overlap_anything(pos):
    return building_at(pos) is not None or road_at(pos) is not None


# ============================
# DRAW BUILDINGS
# ============================
def draw_house(building):
    x = int(building["x"])
    y = int(building["y"])
    pygame.draw.rect(screen, (233, 202, 157), (x - 18, y - 9, 36, 28), border_radius=4)
    pygame.draw.polygon(screen, (166, 86, 58), [(x - 23, y - 10), (x, y - 30), (x + 23, y - 10)])
    pygame.draw.rect(screen, (100, 68, 50), (x - 6, y + 4, 12, 14))
    pygame.draw.rect(screen, (111, 181, 240), (x - 12, y - 4, 7, 9))
    pygame.draw.rect(screen, (111, 181, 240), (x + 5, y - 4, 7, 9))


def draw_hospital(building):
    x = int(building["x"])
    y = int(building["y"])
    pygame.draw.rect(screen, (235, 240, 245), (x - 20, y - 20, 40, 40), border_radius=6)
    pygame.draw.rect(screen, (40, 130, 220), (x - 3, y - 16, 6, 32))
    pygame.draw.rect(screen, (40, 130, 220), (x - 16, y - 3, 32, 6))
    pygame.draw.rect(screen, (255, 255, 255), (x - 7, y + 5, 14, 10))


def draw_fuel_station(building):
    x = int(building["x"])
    y = int(building["y"])
    pygame.draw.rect(screen, (225, 80, 80), (x - 20, y - 20, 40, 40), border_radius=6)
    pygame.draw.circle(screen, (245, 245, 245), (x, y), 12)
    pygame.draw.line(screen, (225, 80, 80), (x, y - 16), (x, y + 16), 3)
    pygame.draw.line(screen, (225, 80, 80), (x - 16, y), (x + 16, y), 3)
    draw_text("F", x - 6, y - 12, WHITE, big_font)


def draw_bridge(building):
    x = int(building["x"])
    y = int(building["y"])
    pygame.draw.rect(screen, (118, 98, 80), (x - 25, y - 10, 50, 14), border_radius=3)
    pygame.draw.rect(screen, (130, 120, 90), (x - 20, y - 22, 8, 22))
    pygame.draw.rect(screen, (130, 120, 90), (x + 12, y - 22, 8, 22))
    pygame.draw.arc(screen, (70, 74, 80), (x - 22, y - 20, 44, 35), 0, math.pi, 4)


def draw_building(building):
    kind = building["type"]
    if kind == "House":
        draw_house(building)
    elif kind == "Hospital":
        draw_hospital(building)
    elif kind == "Fuel Station":
        draw_fuel_station(building)
    elif kind == "Bridge":
        draw_bridge(building)

    draw_text(f"L{building['level']}", building["x"] - 10, building["y"] + 20, BLACK, small_font)

    if selected_object is building:
        pygame.draw.circle(screen, YELLOW, (building["x"], building["y"]), 30, 2)


# ============================
# DRAW ROAD
# ============================
def draw_road(road):
    points = road["points"]
    if len(points) >= 2:
        pygame.draw.lines(screen, ROAD_DARK, False, points, 24)
        pygame.draw.lines(screen, ROAD_LIGHT, False, points, 4)

        for a, b in zip(points, points[1:]):
            pygame.draw.line(screen, (255, 255, 230), a, b, 2)

    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    draw_text(f"L{road['level']}", cx - 10, cy - 8, BLACK, small_font)

    if selected_object is road:
        for p in points:
            pygame.draw.circle(screen, YELLOW, (int(p[0]), int(p[1])), 5, 2)


# ============================
# BUILDING / UPGRADING / CARS
# ============================
def place_building(kind, pos):
    cost = get_building_cost(kind)
    if money < cost:
        show_message("Not enough money!")
        return None

    if maybe_overlap_anything(pos):
        show_message("You cannot build there.")
        return None

    building = {"type": kind, "x": pos[0], "y": pos[1], "level": 1}
    buildings.append(building)
    money -= cost
    selected_object = building
    show_message(f"{kind} built!")
    return building


def upgrade_selected():
    global money, selected_object

    if selected_object is None:
        show_message("Select a road or building first.")
        return

    cost = get_upgrade_cost(selected_object)
    if money < cost:
        show_message("Not enough money to upgrade.")
        return

    money -= cost
    selected_object["level"] += 1
    show_message("Upgraded!")


def create_car():
    usable_roads = [road for road in roads if len(road["points"]) >= 2]
    if not usable_roads:
        return

    road = random.choice(usable_roads)
    route = road["points"][:]
    if random.random() < 0.5:
        route.reverse()

    vehicles.append({
        "route": route,
        "segment": 0,
        "progress": 0.0,
        "x": float(route[0][0]),
        "y": float(route[0][1]),
        "speed": random.uniform(42, 68),
        "color": random.choice([(230, 70, 70), (70, 120, 230), (245, 200, 65), (60, 60, 60), (255, 255, 255)]),
    })


def update_cars(dt):
    for car in vehicles[:]:
        route = car["route"]
        if len(route) < 2:
            vehicles.remove(car)
            continue

        i = car["segment"]
        if i >= len(route) - 1:
            vehicles.remove(car)
            continue

        a = route[i]
        b = route[i + 1]
        seg_len = max(distance(a, b), 1)
        car["progress"] += (car["speed"] * dt) / seg_len

        while car["progress"] >= 1:
            car["progress"] -= 1
            car["segment"] += 1
            if car["segment"] >= len(route) - 1:
                break

        if car["segment"] >= len(route) - 1:
            vehicles.remove(car)
            continue

        a = route[car["segment"]]
        b = route[car["segment"] + 1]
        t = car["progress"]
        car["x"] = a[0] + (b[0] - a[0]) * t
        car["y"] = a[1] + (b[1] - a[1]) * t


# ============================
# SAVE / LOAD
# ============================
def save_game():
    data = {
        "money": money,
        "roads": roads,
        "buildings": buildings,
    }
    try:
        with open(SAVE_FILE, "w") as file:
            json.dump(data, file)
        show_message("City saved!")
    except OSError as error:
        show_message(f"Could not save: {error}")


def load_game():
    global money, roads, buildings, selected_object, vehicles

    if not os.path.exists(SAVE_FILE):
        show_message("No saved city.")
        return

    try:
        with open(SAVE_FILE, "r") as file:
            data = json.load(file)
        money = data.get("money", money)
        roads = data.get("roads", [])
        buildings = data.get("buildings", [])
        selected_object = None
        vehicles = []
        show_message("City loaded!")
    except Exception as error:
        show_message(f"Could not load: {error}")


# ============================
# DRAW GAME
# ============================
def draw_game():
    screen.fill(GRASS)

    # dotted grid
    for x in range(0, MAP_WIDTH + 20, 20):
        for y in range(TOP_BAR, HEIGHT + 20, 20):
            pygame.draw.circle(screen, DOT, (x, y), 2)

    for road in roads:
        draw_road(road)

    if drawing_road is not None and len(drawing_road) >= 2:
        pygame.draw.lines(screen, ROAD_DARK, False, drawing_road, 24)
        pygame.draw.lines(screen, ROAD_LIGHT, False, drawing_road, 4)

    for building in buildings:
        draw_building(building)

    for car in vehicles:
        pygame.draw.rect(screen, car["color"], (int(car["x"]) - 8, int(car["y"]) - 5, 16, 10), border_radius=3)
        pygame.draw.circle(screen, BLACK, (int(car["x"]) - 4, int(car["y"]) + 6), 2)
        pygame.draw.circle(screen, BLACK, (int(car["x"]) + 4, int(car["y"]) + 6), 2)

    # top bar
    pygame.draw.rect(screen, TOP, (0, 0, WIDTH, TOP_BAR))
    draw_text("TINY CITY BUILDER", 16, 16, YELLOW, big_font)
    draw_text(f"Money: ${money}", 470, 18, WHITE)
    draw_text(f"Roads: {len(roads)}", 610, 18, WHITE)
    draw_text(f"Buildings: {len(buildings)}", 780, 18, WHITE)
    draw_text(f"Cars: {len(vehicles)}", 980, 18, WHITE)

    # side panel
    pygame.draw.rect(screen, PANEL, (MAP_WIDTH, 0, PANEL_WIDTH, HEIGHT))
    draw_text("BUILD MENU", MAP_WIDTH + 18, 16, YELLOW, big_font)

    menu = [
        ("Road", "Road"),
        ("House", "House"),
        ("Hospital", "Hospital"),
        ("Fuel Station", "Fuel"),
        ("Bridge", "Bridge"),
        ("Move", "Move"),
    ]

    for i, (key, label) in enumerate(menu):
        y = 70 + i * 48
        rect = (MAP_WIDTH + 14, y, PANEL_WIDTH - 28, 38)
        if selected_tool == key:
            pygame.draw.rect(screen, (70, 90, 80), rect, border_radius=8)
        else:
            pygame.draw.rect(screen, (52, 60, 70), rect, border_radius=8)
        draw_text(label, MAP_WIDTH + 28, y + 9, WHITE, font)

    # upgrade button
    pygame.draw.rect(screen, GREEN, (MAP_WIDTH + 18, 420, PANEL_WIDTH - 36, 42), border_radius=8)
    draw_text("UPGRADE", MAP_WIDTH + 70, 431, WHITE)

    # save/load buttons
    pygame.draw.rect(screen, (64, 111, 160), (MAP_WIDTH + 18, 490, PANEL_WIDTH - 36, 38), border_radius=8)
    draw_text("SAVE", MAP_WIDTH + 92, 500, WHITE)

    pygame.draw.rect(screen, (98, 100, 110), (MAP_WIDTH + 18, 540, PANEL_WIDTH - 36, 38), border_radius=8)
    draw_text("LOAD", MAP_WIDTH + 94, 550, WHITE)

    # selected info
    pygame.draw.line(screen, (200, 220, 220), (MAP_WIDTH + 12, 355), (WIDTH - 12, 355), 1)
    draw_text("SELECTED", MAP_WIDTH + 18, 370, YELLOW, small_font)
    if selected_object is not None:
        if "points" in selected_object:
            draw_text("Road", MAP_WIDTH + 18, 392, WHITE)
        else:
            draw_text(selected_object["type"], MAP_WIDTH + 18, 392, WHITE)
        draw_text(f"Level: {selected_object['level']}", MAP_WIDTH + 18, 418, WHITE)
    else:
        draw_text("Nothing selected", MAP_WIDTH + 18, 392, WHITE)
        draw_text("Click a road or", MAP_WIDTH + 18, 418, WHITE)
        draw_text("building to upgrade", MAP_WIDTH + 18, 440, WHITE)

    if message_timer > 0:
        pygame.draw.rect(screen, TOP, (14, HEIGHT - 42, MAP_WIDTH - 28, 28), border_radius=6)
        draw_text(message, 25, HEIGHT - 35, YELLOW, small_font)


# ============================
# MAIN LOOP
# ============================
while True:
    dt = min(clock.tick(FPS) / 1000.0, 0.05)

    if message_timer > 0:
        message_timer -= dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if mx >= MAP_WIDTH:
                for i, (key, label) in enumerate([
                    ("Road", "Road"),
                    ("House", "House"),
                    ("Hospital", "Hospital"),
                    ("Fuel Station", "Fuel"),
                    ("Bridge", "Bridge"),
                    ("Move", "Move"),
                ]):
                    y = 70 + i * 48
                    if MAP_WIDTH + 14 <= mx <= WIDTH - 14 and y <= my <= y + 38:
                        selected_tool = key
                        dragging_building = None
                        drawing_road = None
                        last_road_point = None

                if MAP_WIDTH + 18 <= mx <= WIDTH - 18 and 420 <= my <= 462:
                    upgrade_selected()

                if MAP_WIDTH + 18 <= mx <= WIDTH - 18 and 490 <= my <= 528:
                    save_game()

                if MAP_WIDTH + 18 <= mx <= WIDTH - 18 and 540 <= my <= 578:
                    load_game()

            elif inside_map((mx, my)):
                pos = snap_point((mx, my))

                if selected_tool == "Road":
                    drawing_road = [pos]
                    last_road_point = pos
                elif selected_tool == "Move":
                    target_building = building_at(pos)
                    target_road = road_at(pos)
                    selected_object = target_building or target_road
                    dragging_building = target_building
                else:
                    target = building_at(pos)
                    if target is not None:
                        selected_object = target
                    else:
                        built = place_building(selected_tool, pos)
                        if built is not None:
                            selected_object = built

        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos

            if drawing_road is not None and inside_map((mx, my)):
                pos = snap_point((mx, my))
                if last_road_point is None or distance(pos, last_road_point) >= 20:
                    drawing_road.append(pos)
                    last_road_point = pos

            if dragging_building is not None and selected_tool == "Move" and inside_map((mx, my)):
                dragging_building["x"] = max(25, min(MAP_WIDTH - 25, mx))
                dragging_building["y"] = max(TOP_BAR + 20, min(HEIGHT - 20, my))

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if drawing_road is not None:
                if len(drawing_road) >= 2:
                    road = {"points": drawing_road, "level": 1}
                    roads.append(road)
                    selected_object = road
                drawing_road = None
                last_road_point = None

            dragging_building = None

    # passive income
    income_timer += dt
    if income_timer >= 1.0:
        income_timer = 0.0
        for item in buildings:
            if item["type"] == "House":
                money += 4 * item["level"]
            elif item["type"] == "Hospital":
                money += 7 * item["level"]
            elif item["type"] == "Fuel Station":
                money += 6 * item["level"]
            elif item["type"] == "Bridge":
                money += 5 * item["level"]

    car_timer += dt
    if car_timer >= 2.2:
        car_timer = 0
        if len(vehicles) < 12 and roads:
            create_car()

    update_cars(dt)
    draw_game()
    pygame.display.flip()
