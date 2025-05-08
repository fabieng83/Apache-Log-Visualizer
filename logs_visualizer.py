import asyncio
import platform
import re
import threading
from queue import Queue
import sys
import pygame
import pymunk
import pymunk.pygame_util
import random
import time
import argparse
from collections import deque

# Configuration
FPS = 60  # Frames per second for the game loop
SCREEN_WIDTH = 1200  # Width of the screen in pixels
SCREEN_HEIGHT = 800  # Height of the screen in pixels
MAIN_AREA_WIDTH = 850  # Width of the physics area on the left
INFO_PANEL_WIDTH = 350  # Width of the info panel on the right
MAX_BALLS = 100  # Maximum number of balls on screen at once
FUNNEL_TOP_Y = 300  # Y-coordinate of the top of the funnel
FUNNEL_END_WIDTH = 150  # Width of the funnel's bottom opening
FUNNEL_CENTER_X = MAIN_AREA_WIDTH / 2  # X-coordinate of the funnel's center
FUNNEL_OPENING_LEFT = FUNNEL_CENTER_X - (FUNNEL_END_WIDTH / 2)  # Left edge of the funnel's bottom opening
FUNNEL_OPENING_RIGHT = FUNNEL_CENTER_X + (FUNNEL_END_WIDTH / 2)  # Right edge of the funnel's bottom opening
GRAVITY = 900  # Gravity strength in the physics simulation
ELASTICITY = 0.9  # Elasticity for collisions (bounciness)
MIN_LINE_SPACING = 20  # Minimum spacing between lines in the info panel
SCROLL_AREA_HEIGHT = SCREEN_HEIGHT - 100  # Height of the scrollable area for URLs
FADE_START_Y = SCROLL_AREA_HEIGHT - (6 * MIN_LINE_SPACING)  # Y-coordinate where fading starts
FADE_END_Y = SCROLL_AREA_HEIGHT  # Y-coordinate where fading ends (text becomes fully transparent)
MAX_URL_LENGTH = 35  # Maximum length for displayed URLs
MAX_BALL_RADIUS = 60  # Maximum radius for balls to prevent oversized balls
SUBSTEPS = 5  # Number of physics substeps per frame for better collision detection
WALL_THICKNESS = 10  # Thickness of the funnel walls (increased to prevent clipping)
DESPAWN_TIME = 10  # Time in seconds after which objects are despawned if still on screen
BALL_SPAWN_VX = -250  # Base horizontal spawn velocity for balls (negative for leftward motion)
BALL_SPAWN_VX_RANGE = (-200, 100)  # Randomization range for horizontal spawn velocity

# Function: format_size
# Description: Converts a byte size into a human-readable format (e.g., B, KB, MB, GB, TB).
def format_size(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    converted_size = float(size)
    # Iterate through units until the size is less than 1024 or we run out of units
    while converted_size >= 1024 and unit_index < len(units) - 1:
        converted_size /= 1024
        unit_index += 1
    return f"{converted_size:.1f} {units[unit_index]}"



class LogVisualizer:
    def __init__(self, test_mode=False):
        # Initialize Pygame for rendering graphics
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Log Visualizer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 14)
        
        # Initialize Pymunk for physics simulation
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        # Improve collision detection accuracy
        self.space.collision_bias = 0.0001  # Reduce bias for more precise collisions
        self.space.iterations = 20  # Increase iterations for better collision resolution
        
        # Create funnel walls as static segments with increased thickness
        static_body = self.space.static_body
        self.left_wall = pymunk.Segment(static_body, (0, FUNNEL_TOP_Y), (FUNNEL_OPENING_LEFT, SCREEN_HEIGHT), WALL_THICKNESS)
        self.right_wall = pymunk.Segment(static_body, (MAIN_AREA_WIDTH, FUNNEL_TOP_Y), (FUNNEL_OPENING_RIGHT, SCREEN_HEIGHT), WALL_THICKNESS)
        self.left_wall.elasticity = ELASTICITY
        self.right_wall.elasticity = ELASTICITY
        self.space.add(self.left_wall, self.right_wall)
        
        # Initialize log queue and stats
        self.log_queue = Queue()  # Queue to hold incoming log data
        self.balls = []  # List to store active balls
        self.recent_urls = []  # List to store recent URLs (not limited)
        self.url_positions = []  # List to store URL positions for scrolling
        self.request_times = deque(maxlen=3600)  # Store timestamps of requests (last 1 hour)
        self.max_size_seen = 1000  # Track the largest request size seen
        self.colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (255, 0, 255), (0, 255, 255)
        ]  # Colors for the balls
        self.white = (255, 255, 255)  # White color for text
        self.black = (0, 0, 0)  # Black color for background
        self.prasin_green = (102, 255, 102)  # Prasin green for request sizes
        self.test_mode = test_mode  # Flag for test mode (simulated logs)

    # Function: extract_log_info
    # Description: Extracts relevant information (method, URL, status, size) from a log line using regex.
    def extract_log_info(self, line):
        match = re.search(r'"(\S+) (\S+) \S+" (\d+) (\d+|-)', line)
        if match:
            method = match.group(1)
            url = match.group(2)
            status = int(match.group(3))
            size_str = match.group(4)
            # Convert size to 0 if it's a dash (indicating no size)
            size = 0 if size_str == '-' else int(size_str)
            # Remove query parameters from URL
            url = url.split('?')[0]
            return {'method': method, 'url': url, 'status': status, 'size': size}
        return None

    # Function: tail_logs
    # Description: Reads log lines from stdin (e.g., from a tail command) and adds them to the log queue.
    def tail_logs(self):
        for line in sys.stdin:
            log_data = self.extract_log_info(line)
            if log_data:
                self.log_queue.put(log_data)
                self.request_times.append(time.time())

    # Function: simulate_logs
    # Description: Simulates fake log requests in test mode (15 to 20 requests per second).
    def simulate_logs(self):
        methods = ['GET', 'POST', 'DELETE']
        statuses = [200, 404]
        urls = ['/page1', '/page2', '/api/data', '/images/img.jpg', '/login', '/logout']
        
        while True:
            # Sleep for 50 to 66 milliseconds to achieve 15-20 requests per second
            time.sleep(random.uniform(0.05, 0.066))
            method = random.choice(methods)
            url = random.choice(urls)
            status = random.choice(statuses)
            size = random.randint(0, 100000)
            log_data = {'method': method, 'url': url, 'status': status, 'size': size}
            self.log_queue.put(log_data)
            self.request_times.append(time.time())

    # Function: draw_shape
    # Description: Draws a physics shape (circle, polygon, or segment) with a colored outline.
    def draw_shape(self, shape, color):
        if isinstance(shape, pymunk.Circle):
            pos = shape.body.position
            radius = shape.radius
            pygame.draw.circle(self.screen, color, (int(pos.x), int(pos.y)), int(radius), 2)
        elif isinstance(shape, pymunk.Poly):
            # Convert vertices to screen coordinates
            vertices = [shape.body.position + v.rotated(shape.body.angle) for v in shape.get_vertices()]
            points = [(int(v.x), int(v.y)) for v in vertices]
            pygame.draw.polygon(self.screen, color, points, 2)
        elif isinstance(shape, pymunk.Segment):
            # Draw a line segment for the funnel walls
            p1 = shape.body.position + shape.a.rotated(shape.body.angle)
            p2 = shape.body.position + shape.b.rotated(shape.body.angle)
            pygame.draw.line(self.screen, color, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 6)

    class Ball:
        # Function: __init__
        # Description: Initializes a new ball with properties based on the log data (method, status, size).
        def __init__(self, visualizer, log_data):
            self.url = log_data.get('url', '')
            self.status = log_data.get('status', 200)
            self.size = log_data.get('size', 0)
            self.method = log_data.get('method', 'GET')
            self.color = random.choice(visualizer.colors)
            # Record the spawn time for despawning logic
            self.spawn_time = time.time()
            
            # Calculate the ball's radius based on the request size relative to the max size seen
            if visualizer.max_size_seen > 0:
                # Limit scale to 1.0 to prevent oversized balls
                scale = min(self.size / visualizer.max_size_seen, 1.0)
                radius_range = MAX_BALL_RADIUS - 15
                self.radius = 15 + (scale * radius_range)
            else:
                self.radius = 15
            # Ensure the radius never exceeds MAX_BALL_RADIUS
            self.radius = min(self.radius, MAX_BALL_RADIUS)
            # Fixed radius for POST, DELETE, and 404 requests
            if self.status == 404 or self.method in ['POST', 'DELETE']:
                self.radius = 15
            # Calculate mass based on radius (affects physics behavior)
            mass = self.radius ** 2 if self.method not in ['POST', 'DELETE'] else 1
            
            # Define the shape based on the request method and status
            if self.method == 'POST':
                arrow_vertices = [(0, -15), (10, 5), (5, 5), (5, 15), (-5, 15), (-5, 5), (-10, 5), (0, -15)]
                scale_factor = 2
                scaled_arrow_vertices = [(x * scale_factor, y * scale_factor) for x, y in arrow_vertices]
                
                inertia = pymunk.moment_for_poly(mass, arrow_vertices)
                self.body = pymunk.Body(mass, inertia)
                self.arrow_shape = pymunk.Poly(self.body, arrow_vertices)
                self.arrow_shape.elasticity = ELASTICITY
                self.arrow_shape.friction = 0.5
                self.arrow_shape.color = self.color + (255,)
            elif self.method == 'DELETE':
                # Create an "X" shape for DELETE requests
                self.body = pymunk.Body(mass, pymunk.moment_for_box(mass, (30, 30)))
                branch_width = 10
                half_width = branch_width / 2
                # Define the two diagonal branches of the "X"
                vertices1 = [
                    (-15 - half_width, -15 + half_width),
                    (-15 + half_width, -15 - half_width),
                    (15 + half_width, 15 - half_width),
                    (15 - half_width, 15 + half_width),
                ]
                self.shape1 = pymunk.Poly(self.body, vertices1)
                vertices2 = [
                    (-15 - half_width, 15 - half_width),
                    (-15 + half_width, 15 + half_width),
                    (15 + half_width, -15 + half_width),
                    (15 - half_width, -15 - half_width),
                ]
                self.shape2 = pymunk.Poly(self.body, vertices2)
                self.shape1.elasticity = ELASTICITY
                self.shape1.friction = 0.5
                self.shape2.elasticity = ELASTICITY
                self.shape2.friction = 0.5
                self.shape1.color = self.color + (255,)
                self.shape2.color = self.color + (255,)
            elif self.status == 404:
                # Create a square shape for 404 status requests
                vertices = [(-15, -15), (15, -15), (15, 15), (-15, 15)]
                inertia = pymunk.moment_for_poly(mass, vertices)
                self.body = pymunk.Body(mass, inertia)
                self.shape = pymunk.Poly(self.body, vertices)
            else:
                # Create a circle shape for all other requests
                inertia = pymunk.moment_for_circle(mass, 0, self.radius)
                self.body = pymunk.Body(mass, inertia)
                self.shape = pymunk.Circle(self.body, self.radius)
            
            # Set the initial position in the top-right corner of the physics area
            self.body.position = (MAIN_AREA_WIDTH - 20 - self.radius, random.uniform(20, 50))
            # Set initial velocity using BALL_SPAWN_VX with randomization
            vx = BALL_SPAWN_VX + random.uniform(BALL_SPAWN_VX_RANGE[0], BALL_SPAWN_VX_RANGE[1])
            vy = random.uniform(-50, 50)
            self.body.velocity = (vx, vy)
            
            # Apply physical properties to the main shape
            if self.method not in ['POST', 'DELETE']:
                self.shape.elasticity = ELASTICITY
                self.shape.friction = 0.5
                self.shape.color = self.color + (255,)
            
            # Add the shape to the physics space
            if self.method == 'POST':
                visualizer.space.add(self.body, self.arrow_shape)
            elif self.method == 'DELETE':
                visualizer.space.add(self.body, self.shape1, self.shape2)
            else:
                visualizer.space.add(self.body, self.shape)
            self.visualizer = visualizer

    # Function: run
    # Description: Main game loop that handles events, updates physics, and renders the visualization.
    async def run(self):
        # Start the log reading or simulation thread
        if self.test_mode:
            log_thread = threading.Thread(target=self.simulate_logs)
        else:
            log_thread = threading.Thread(target=self.tail_logs)
        log_thread.daemon = True
        log_thread.start()
        
        running = True
        while running:
            # Handle Pygame events (e.g., quitting, key presses)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    # Reset max_size_seen when the 'R' key is pressed
                    self.max_size_seen = 1000
            
            # Add new balls from the log queue
            while not self.log_queue.empty() and len(self.balls) < MAX_BALLS:
                log_data = self.log_queue.get()
                self.balls.append(self.Ball(self, log_data))
                # Update the largest request size seen
                self.max_size_seen = max(self.max_size_seen, log_data['size'])
                self.recent_urls.append((log_data['url'], log_data['size']))
                # Shift all existing URLs downward
                for i in range(len(self.url_positions)):
                    url, size, y_pos = self.url_positions[i]
                    y_pos += MIN_LINE_SPACING
                    self.url_positions[i] = (url, size, y_pos)
                # Remove URLs that have scrolled off the bottom
                for i in range(len(self.url_positions) - 1, -1, -1):
                    url, size, y_pos = self.url_positions[i]
                    if y_pos >= SCROLL_AREA_HEIGHT:
                        self.url_positions.pop(i)
                # Add the new URL at the top
                self.url_positions.append((log_data['url'], log_data['size'], 20))
            
            # Update the physics simulation with substeps for better accuracy
            dt = 1.0 / FPS / SUBSTEPS
            for _ in range(SUBSTEPS):
                self.space.step(dt)
            
            # Remove balls that exit through the funnel's bottom opening or are too old
            current_time = time.time()
            for ball in self.balls[:]:
                pos = ball.body.position
                # Check if the ball exits through the funnel
                if (pos.y > SCREEN_HEIGHT and 
                    FUNNEL_OPENING_LEFT <= pos.x <= FUNNEL_OPENING_RIGHT):
                    if ball.method == 'POST':
                        self.space.remove(ball.arrow_shape, ball.body)
                    elif ball.method == 'DELETE':
                        self.space.remove(ball.shape1, ball.shape2, ball.body)
                    else:
                        self.space.remove(ball.shape, ball.body)
                    self.balls.remove(ball)
                # Despawn balls that have been on screen for more than DESPAWN_TIME seconds
                elif (current_time - ball.spawn_time) > DESPAWN_TIME:
                    if ball.method == 'POST':
                        self.space.remove(ball.arrow_shape, ball.body)
                    elif ball.method == 'DELETE':
                        self.space.remove(ball.shape1, ball.shape2, ball.body)
                    else:
                        self.space.remove(ball.shape, ball.body)
                    self.balls.remove(ball)
            
            # Clear the screen
            self.screen.fill(self.black)
            
            # Draw the funnel walls
            self.draw_shape(self.left_wall, self.white)
            self.draw_shape(self.right_wall, self.white)
            
            # Draw all balls
            for ball in self.balls:
                if ball.method == 'POST':
                    self.draw_shape(ball.arrow_shape, ball.color)
                elif ball.method == 'DELETE':
                    self.draw_shape(ball.shape1, ball.color)
                    self.draw_shape(ball.shape2, ball.color)
                else:
                    self.draw_shape(ball.shape, ball.color)
            
            # Draw status text on each ball
            for ball in self.balls:
                pos = ball.body.position
                text_surface = self.font.render(str(ball.status), True, self.white)
                # Center the status text on the ball
                self.screen.blit(text_surface, (int(pos.x - text_surface.get_width() // 2), int(pos.y - text_surface.get_height() // 2)))
            
            # Draw the info panel background
            pygame.draw.rect(self.screen, (50, 50, 50), (MAIN_AREA_WIDTH, 0, INFO_PANEL_WIDTH, SCREEN_HEIGHT))
            
            # Draw URLs and sizes with a fading effect near the stats area
            for url, size, y_pos in self.url_positions:
                if y_pos < SCROLL_AREA_HEIGHT:
                    alpha = 255
                    if y_pos >= FADE_START_Y:
                        # Calculate fading: linearly reduce alpha from 255 to 0 between FADE_START_Y and FADE_END_Y
                        fade_distance = FADE_END_Y - FADE_START_Y
                        distance_from_fade_start = y_pos - FADE_START_Y
                        alpha = int(255 * (1 - (distance_from_fade_start / fade_distance)))
                        alpha = max(0, min(255, alpha))
                    
                    # Truncate the URL if it exceeds MAX_URL_LENGTH
                    url_display = f"{url[:MAX_URL_LENGTH]}..." if len(url) > MAX_URL_LENGTH else url
                    url_text = self.font.render(url_display, True, self.white)
                    size_str = format_size(size)
                    size_text = self.font.render(size_str, True, self.prasin_green)
                    
                    # Apply the fading effect to both URL and size text
                    url_text.set_alpha(alpha)
                    size_text.set_alpha(alpha)
                    
                    # Draw the URL on the left and the size on the right
                    self.screen.blit(url_text, (MAIN_AREA_WIDTH + 10, int(y_pos)))
                    self.screen.blit(size_text, (MAIN_AREA_WIDTH + INFO_PANEL_WIDTH - size_text.get_width() - 10, int(y_pos)))
            
            # Display stats at the bottom of the info panel
            y_offset = SCREEN_HEIGHT - 100
            # Calculate request rates (requests per minute and per second)
            current_time = time.time()
            recent_requests = sum(1 for t in self.request_times if current_time - t < 60)
            stats = [
                f"Max Size: {format_size(self.max_size_seen)}",
                f"Requests/min: {recent_requests}",
            ]
            recent_requests = sum(1 for t in self.request_times if current_time - t < 1)
            stats.append(f"Requests/sec: {recent_requests}")
            
            # Draw each stat line
            for stat in stats:
                text = self.font.render(stat, True, self.white)
                self.screen.blit(text, (MAIN_AREA_WIDTH + 10, y_offset))
                y_offset += 20
            
            # Update the display
            pygame.display.flip()
            self.clock.tick(FPS)
            await asyncio.sleep(1.0 / FPS)
        
        # Clean up Pygame resources
        pygame.quit()

# Main execution block for Pyodide compatibility
if platform.system() == "Emscripten":
    parser = argparse.ArgumentParser(description="Log Visualizer")
    parser.add_argument('--test', action='store_true', help="Run in test mode with simulated requests")
    args = parser.parse_args()

    visualizer = LogVisualizer(test_mode=args.test)
    asyncio.ensure_future(visualizer.run())
else:
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Log Visualizer")
        parser.add_argument('--test', action='store_true', help="Run in test mode with simulated requests")
        args = parser.parse_args()

        visualizer = LogVisualizer(test_mode=args.test)
        asyncio.run(visualizer.run())
