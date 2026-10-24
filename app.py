
try:
    pygame = __import__("pygame")
except ModuleNotFoundError as exc:
    if exc.name != "pygame":
        raise
    raise SystemExit(
        "Pygame is required to run this application. Install it with: python -m pip install pygame"
    ) from exc
import random
import math
import json
import os
import sys

pygame.init()

# ==================================================
# SETTINGS
# ==================================================
WIDTH, HEIGHT = 1200, 760
PANEL_WIDTH = 220
MAP_WIDTH = WIDTH - PANEL_WIDTH
TOP_BAR = 65

FPS = 120
ROAD_WIDTH = 24

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("My City Builder")
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 17)
small_font = pygame.font.SysFont("arial", 13)
large_font = pygame.font.SysFont("arial", 24)

# ==================================================
# COLORS
# ==================================================
GRASS = (125, 175, 105)
GRID = (140, 185, 120)
ROAD_COLOR = (65, 68, 74)
ROAD_LINE = (190, 190, 175)
WHITE = (245, 245, 240)
BLACK = (30, 35, 35)
GOLD = (255, 210, 75)
BLUE = (65, 150, 235)
RED = (220, 80, 70)
GREEN = (65, 180, 100)

# ==================================================
# GAME DATA
# ==================================================
money = 1500
population = 12

prices = {
    "House": 100,
    "Toll": 150,
    "Fuel": 200,
    "Hospital": 250,
    "Shop": 150,
}

business_income = {
    "Fuel": 3,
    "Hospital": 2,
    "Shop": 4,
}

# Roads are freehand strokes, not grid tiles.
roads = []

# Buildings are positioned freely on the map.
buildings = [
    {"type": "House", "x": 150, "y": 160, "level": 1},
    {"type": "House", "x": 300, "y": 220, "level": 1},
    {"type": "House", "x": 470, "y": 145, "level": 1},
    {"type": "House", "x": 210, "y": 410, "level": 1},
    {"type": "House", "x": 530, "y": 440, "level": 1},
]

vehicles = []

tool = "Move"
selected_building = None
dragging_building = None
drawing_road = None
last_draw_point = None

car_timer = 0
income_timer = 0
message = ""
message_timer = 0

SAVE_FILE = "city_save.json"

# ==================================================
# HELPERS
# ==================================================
def draw_text(text, x, y, color=WHITE, f=font):
    image = f.render(str(text), True, color)
    screen.blit(image, (int(x), int(y)))


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def inside_map(pos):
    x, y = pos
    return 0 <= x < MAP_WIDTH and TOP_BAR <= y < HEIGHT


def building_at(pos):
    for building in reversed(buildings):
        if distance(
            pos, (building["x"], building["y"])
        ) < 28:
            return building
    return None


def show_message(text):
    global message, message_timer
    message = text
    message_timer = 2.5


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


# ==================================================
# ROAD HELPERS
# ==================================================
def find_nearest_road(pos, max_distance=45):
    best = None
    best_distance = max_distance

    for road in roads:
        for i in range(len(road) - 1):
            point = nearest_point_on_segment(
                pos, road[i], road[i + 1]
            )
            d = distance(pos, point)

            if d < best_distance:
                best_distance = d
                best = (road, i, point)

    return best


def create_car():
    # Cars follow a complete drawn road stroke.
    usable_roads = [
        road for road in roads
        if len(road) >= 2
        and sum(
            distance(road[i], road[i + 1])
            for i in range(len(road) - 1)
        ) >= 100
    ]

    if not usable_roads:
        return

    road = random.choice(usable_roads)

    if random.choice([True, False]):
        route = list(reversed(road))
    else:
        route = list(road)

    # Avoid excessive route complexity.
    if len(route) > 1500:
        route = route[::2]

    vehicles.append({
        "route": route,
        "segment": 0,
        "progress": 0.0,
        "x": float(route[0][0]),
        "y": float(route[0][1]),
        "speed": random.uniform(55, 85),
        "color": random.choice([
            (240, 235, 220),
            (225, 80, 70),
            (70, 120, 230),
            (240, 195, 60),
            (55, 55, 55),
        ]),
        "paid_tolls": set(),
    })


def update_cars(dt):
    global money

    for car in vehicles[:]:
        route = car["route"]
        i = car["segment"]

        if i >= len(route) - 1:
            vehicles.remove(car)
            continue

        a = route[i]
        b = route[i + 1]
        segment_length = max(distance(a, b), 0.1)

        car["progress"] += (
            car["speed"] * dt / segment_length
        )

        while car["progress"] >= 1:
            car["progress"] -= 1
            car["segment"] += 1

            if car["segment"] >= len(route) - 1:
                break

        i = car["segment"]

        if i >= len(route) - 1:
            vehicles.remove(car)
            continue

        a = route[i]
        b = route[i + 1]
        t = car["progress"]

        car["x"] = a[0] + (b[0] - a[0]) * t
        car["y"] = a[1] + (b[1] - a[1]) * t

        # A vehicle pays each toll at most once per journey.
        for index, building in enumerate(buildings):
            if building["type"] != "Toll":
                continue

            key = id(building)

            if (
                distance(
                    (car["x"], car["y"]),
                    (building["x"], building["y"])
                ) < 27
                and key not in car["paid_tolls"]
            ):
                money += 5 * building["level"]
                car["paid_tolls"].add(key)


# ==================================================
# BUILDINGS
# ==================================================
def draw_building(building):
    x = int(building["x"])
    y = int(building["y"])
    kind = building["type"]
    level = building["level"]

    if kind == "House":
        # House body and roof.
        pygame.draw.rect(
            screen, (235, 205, 160),
            (x - 17, y - 10, 34, 27)
        )
        pygame.draw.polygon(
            screen, (160, 75, 60),
            [(x - 22, y - 9), (x, y - 29), (x + 22, y - 9)]
        )
        pygame.draw.rect(
            screen, (110, 75, 45),
            (x - 5, y + 4, 10, 13)
        )
        pygame.draw.rect(
            screen, (100, 180, 220),
            (x - 13, y - 5, 7, 8)
        )
        pygame.draw.rect(
            screen, (100, 180, 220),
            (x + 6, y - 5, 7, 8)
        )

    else:
        colors = {
            "Toll": GOLD,
            "Fuel": RED,
            "Hospital": WHITE,
            "Shop": BLUE,
        }

        pygame.draw.rect(
            screen, colors[kind],
            (x - 19, y - 19, 38, 38),
            border_radius=5
        )

        labels = {
            "Toll": "$",
            "Fuel": "F",
            "Hospital": "+",
            "Shop": "S",
        }

        draw_text(
            labels[kind], x - 7, y - 12,
            BLACK, large_font
        )

    draw_text(
        f"L{level}", x - 9, y + 22,
        WHITE, small_font
    )

    if building is selected_building:
        pygame.draw.circle(
            screen, GOLD, (x, y), 32, 2
        )


def place_building(kind, pos):
    global money, selected_building, dragging_building

    if money < prices[kind]:
        show_message("Not enough money!")
        return

    if building_at(pos):
        show_message("There is already a building here.")
        return

    building = {
        "type": kind,
        "x": pos[0],
        "y": pos[1],
        "level": 1,
    }

    buildings.append(building)
    money -= prices[kind]
    selected_building = building
    dragging_building = building

    show_message(kind + " built!")


def upgrade_selected():
    global money

    if selected_building not in buildings:
        show_message("Select a building first.")
        return

    cost = selected_building["level"] * 100

    if money < cost:
        show_message("Not enough money to upgrade!")
        return

    money -= cost
    selected_building["level"] += 1

    show_message("Building upgraded!")


# ==================================================
# SAVE AND LOAD
# ==================================================
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
    except (OSError, TypeError) as error:
        show_message("Could not save: " + str(error))


def load_game():
    global money, roads, buildings
    global selected_building, vehicles

    if not os.path.exists(SAVE_FILE):
        show_message("No saved city found.")
        return

    try:
        with open(SAVE_FILE, "r") as file:
            data = json.load(file)

        money = data["money"]
        roads = data["roads"]
        buildings = data["buildings"]

        selected_building = None
        vehicles = []

        show_message("City loaded!")
    except (OSError, ValueError, KeyError) as error:
        show_message("Could not load: " + str(error))


# ==================================================
# DRAW THE WHOLE GAME
# ==================================================
def draw_game():
    screen.fill(GRASS)

    # Faint grid: background only, not building tiles.
    for x in range(0, MAP_WIDTH, 25):
        pygame.draw.line(
            screen, GRID, (x, TOP_BAR), (x, HEIGHT)
        )

    for y in range(TOP_BAR, HEIGHT, 25):
        pygame.draw.line(
            screen, GRID, (0, y), (MAP_WIDTH, y)
        )

    # Roads.
    for road in roads:
        if len(road) >= 2:
            pygame.draw.lines(
                screen, ROAD_COLOR, False, road, ROAD_WIDTH
            )
            pygame.draw.lines(
                screen, ROAD_LINE, False, road, 2
            )

    # Road currently being drawn.
    if drawing_road and len(drawing_road) >= 2:
        pygame.draw.lines(
            screen, ROAD_COLOR, False,
            drawing_road, ROAD_WIDTH
        )
        pygame.draw.lines(
            screen, ROAD_LINE, False,
            drawing_road, 2
        )

    # Houses and other buildings.
    for building in buildings:
        draw_building(building)

    # Vehicles.
    for car in vehicles:
        x, y = int(car["x"]), int(car["y"])

        pygame.draw.rect(
            screen, car["color"],
            (x - 7, y - 5, 14, 10),
            border_radius=3
        )

        pygame.draw.circle(
            screen, BLACK, (x - 4, y + 5), 2
        )
        pygame.draw.circle(
            screen, BLACK, (x + 4, y + 5), 2
        )

    # Top bar.
    pygame.draw.rect(
        screen, (40, 45, 50),
        (0, 0, WIDTH, TOP_BAR)
    )

    draw_text("MY CITY BUILDER", 14, 7, GOLD)
    draw_text(f"Money: ${int(money)}", 14, 36)
    draw_text(f"Buildings: {len(buildings)}", 190, 36)
    draw_text(f"Cars: {len(vehicles)}", 340, 36)

    # Toolbar.
    pygame.draw.rect(
        screen, (43, 48, 56),
        (MAP_WIDTH, 0, PANEL_WIDTH, HEIGHT)
    )

    draw_text("BUILD MENU", MAP_WIDTH + 15, 12, GOLD)

    options = [
        ("Move", "Move buildings"),
        ("Road", "Draw roads"),
        ("House", "House  $100"),
        ("Toll", "Toll booth  $150"),
        ("Fuel", "Fuel station  $200"),
        ("Hospital", "Hospital  $250"),
        ("Shop", "Shop  $150"),
    ]

    for i, (key, label) in enumerate(options):
        y = 47 + i * 43

        if tool == key:
            pygame.draw.rect(
                screen, (80, 100, 80),
                (MAP_WIDTH + 7, y - 4, PANEL_WIDTH - 14, 35),
                border_radius=5
            )

        draw_text(
            label, MAP_WIDTH + 15, y + 3,
            GOLD if tool == key else WHITE,
            small_font
        )

    pygame.draw.line(
        screen, WHITE,
        (MAP_WIDTH + 10, 355),
        (WIDTH - 10, 355), 1
    )

    draw_text(
        "SELECTED BUILDING",
        MAP_WIDTH + 12, 367, GOLD, small_font
    )

    if selected_building in buildings:
        b = selected_building

        draw_text(b["type"], MAP_WIDTH + 12, 393)
        draw_text(
            f"Level: {b['level']}",
            MAP_WIDTH + 12, 419
        )

        cost = b["level"] * 100
        draw_text(
            f"Upgrade: ${cost}",
            MAP_WIDTH + 12, 445, GOLD, small_font
        )

        pygame.draw.rect(
            screen, GREEN,
            (MAP_WIDTH + 10, 470, PANEL_WIDTH - 20, 36),
            border_radius=5
        )
        draw_text(
            "UPGRADE", MAP_WIDTH + 65, 479,
            WHITE, small_font
        )

    else:
        draw_text(
            "Select a building", MAP_WIDTH + 12, 402,
            WHITE, small_font
        )
        draw_text(
            "to see upgrades.", MAP_WIDTH + 12, 422,
            WHITE, small_font
        )

    # Save/load controls.
    pygame.draw.rect(
        screen, (65, 105, 160),
        (MAP_WIDTH + 10, 535, PANEL_WIDTH - 20, 35),
        border_radius=5
    )
    draw_text(
        "SAVE CITY", MAP_WIDTH + 68, 544,
        WHITE, small_font
    )

    pygame.draw.rect(
        screen, (100, 100, 110),
        (MAP_WIDTH + 10, 578, PANEL_WIDTH - 20, 35),
        border_radius=5
    )
    draw_text(
        "LOAD CITY", MAP_WIDTH + 68, 587,
        WHITE, small_font
    )

    draw_text(
        "Drag to draw roads", MAP_WIDTH + 12, 640,
        WHITE, small_font
    )
    draw_text(
        "Drag buildings to move", MAP_WIDTH + 12, 660,
        WHITE, small_font
    )

    if message_timer > 0:
        pygame.draw.rect(
            screen, (40, 45, 50),
            (15, HEIGHT - 43, MAP_WIDTH - 30, 30),
            border_radius=5
        )
        draw_text(message, 25, HEIGHT - 37, GOLD, small_font)


# ==================================================
# MAIN GAME LOOP
# ==================================================
while True:
    dt = min(clock.tick(FPS) / 1000, 0.05)

    if message_timer > 0:
        message_timer -= dt

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        # ------------------------------------------
        # MOUSE DOWN
        # ------------------------------------------
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            mx, my = event.pos

            if mx >= MAP_WIDTH:
                # Select a tool.
                options = [
                    "Move", "Road", "House", "Toll",
                    "Fuel", "Hospital", "Shop"
                ]

                for i, key in enumerate(options):
                    y = 47 + i * 43

                    if y - 4 <= my <= y + 31:
                        tool = key
                        dragging_building = None
                        drawing_road = None

                # Upgrade.
                if (
                    470 <= my <= 506
                    and selected_building in buildings
                ):
                    upgrade_selected()

                # Save city.
                if 535 <= my <= 570:
                    save_game()

                # Load city.
                if 578 <= my <= 613:
                    load_game()

            elif inside_map((mx, my)):
                pos = (mx, my)

                if tool == "Road":
                    drawing_road = [pos]
                    last_draw_point = pos

                elif tool == "Move":
                    selected_building = building_at(pos)
                    dragging_building = selected_building

                else:
                    place_building(tool, pos)

        # ------------------------------------------
        # MOUSE MOVE
        # ------------------------------------------
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos

            # Draw a continuous road.
            if (
                drawing_road is not None
                and inside_map((mx, my))
            ):
                if distance(
                    (mx, my), last_draw_point
                ) >= 5:
                    drawing_road.append((mx, my))
                    last_draw_point = (mx, my)

            # Move buildings freely.
            if (
                dragging_building is not None
                and tool == "Move"
                and inside_map((mx, my))
            ):
                dragging_building["x"] = max(25, min(MAP_WIDTH - 25, mx))
                dragging_building["y"] = max(TOP_BAR + 30, min(HEIGHT - 30, my))

            # Newly built buildings can be positioned
            # immediately by dragging.
            elif (
                dragging_building is not None
                and tool not in ("Move", "Road")
                and inside_map((mx, my))
            ):
                dragging_building["x"] = max(25, min(MAP_WIDTH - 25, mx))
                dragging_building["y"] = max(TOP_BAR + 30, min(HEIGHT - 30, my))

        # ------------------------------------------
        # MOUSE UP
        # ------------------------------------------
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
        ):
            if drawing_road is not None:
                if len(drawing_road) >= 2:
                    roads.append(drawing_road)

                drawing_road = None
                last_draw_point = None

            dragging_building = None

    # Passive business income.
    income_timer += dt

    if income_timer >= 1:
        income_timer -= 1

        for b in buildings:
            kind = b["type"]

            if kind in business_income:
                money += business_income[kind] * b["level"]

    # Automatically spawn traffic.
    car_timer += dt

    if car_timer >= 2:
        car_timer = 0

        if len(vehicles) < 20:
            create_car()

    update_cars(dt)

    draw_game()
    pygame.display.flip()
   