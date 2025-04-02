#In dieser Datei befindet sich die wichtigste Logik für das Simulations-Programm

#Import von Frameworks (Programmbibliotheken)
import pygame, sys, random, math
import time, threading 
from settings import *
import save_data
import psutil

class Simulation:
    #Die Klasse Simulation erzweugt das Pygame-Fenster sowie die gesamte Logik hinter dem Simulations-Programm

    def __init__(self):
        #In dieser Funktion werden für die Simulation wichtige Variablen deklariert 
        pygame.init()
        pygame.font.init()
        pygame.mixer.init()
        self.my_font = pygame.font.SysFont('Inter', 30)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("SIR-Simulation")


        self.creature_list = []
        self.total_amount = len(self.creature_list)
        self.sick_creature_amount = 0
        self.healthy_creature_amount = 0
        self.immune_creature_amount = 0
        self.sick_creature_peak = 0
        
        self.shuting_down = False
        self.shut_down_timer = 0

        self.distance_grid_cell_list = []
        self.distance_grid = {}  # {(grid_x, grid_y): [creatures]}

        self.infecting_animation_circles = []
        first_data = Data(1 - INFECTED_PERCENTAGE_AT_START, INFECTED_PERCENTAGE_AT_START, 0.0)
        self.data_set = [first_data]

        self.moving_status = True
        self.quarantine_bool = QUARANTINE

        self.line_indicator_bool = False
        self.indicator_once_bool = True
        self.line_indicator_data = None

        self.seconds_running = 0
        
        self.recent_infections_counter = 0
        self.active_infected = POPULATION_SIZE * INFECTED_PERCENTAGE_AT_START
        self.r_naught = 0
        self.last_infection_update_time = pygame.time.get_ticks()

        self.zeit_vergangen = 0

    def run_simulation(self):
        #Diese Funktion ist für den 'Game-Loop' zuständig. In ihr werden alle Funktionen der Simulation periodisch aufgerufen

        self.spawn_creatures()
        self.last_distance_check = pygame.time.get_ticks()
        self.chart_update_timer = pygame.time.get_ticks()
        self.last_r_update = pygame.time.get_ticks()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.shutdown()

                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.indicator_once_bool:
                    print("Quaränte-Maßnahme aktiv!")
                    self.quarantine_bool = True
                    self.line_indicator_bool = True
                    self.data_set[-1].indicator = True
                    self.indicator_once_bool = False
                    for creature in self.creature_list:
                        if creature.health_status == "sick":
                            creature.quarantine_timer_start()

            self.display_statistic()
        

            if ANIMATIONEN:
                self.infecting_animation()
            self.render_graphics()
            self.display_chart_rects()
            self.statistic_timer()
            self.draw_axes()
            if VERSAMMLUNGS_HOTSPOT:
                self.draw_hotspot_zone()
            if self.quarantine_bool:
                self.quarantäne()
            self.check_distances()
            self.update_r_naught()
            if AUTO_SHUTDOWN:
                self.check_game_over()
            pygame.display.update()
            self.screen.fill(BG_COLOR)
            self.dt = self.clock.tick()
            self.zeit_vergangen += self.dt

    def render_graphics(self):
        #Diese Funktion zeichnet die Kreaturen und berechnet ihre Positionen
        pygame.draw.line(self.screen, LINIEN_FARBE, (SCREEN_WIDTH//2, 0), (SCREEN_WIDTH//2, SCREEN_HEIGHT), 2) #trenn linie zeichnen

        for creature in self.creature_list:
            color = HEALTHY_CREATURE_COLOR
            if creature.health_status == "sick":
                color = SICK_CREATURE_COLOR
            elif creature.health_status == "immune":
                color = IMMUNE_CREATURE_COLOR
            #pygame.draw.circle(self.screen, color, (creature.position), CREATURE_SIZE)
            
            rect = pygame.Rect(creature.position[0] - CREATURE_SIZE/2, creature.position[1] - CREATURE_SIZE/2, CREATURE_SIZE, CREATURE_SIZE)
            pygame.draw.rect(self.screen, color, rect)

        
        if self.moving_status:
            for creature in self.creature_list:
                # Calculate distance to target
                distance = math.sqrt((creature.destination[0] - creature.position[0])**2 + (creature.destination[1] - creature.position[1])**2)
                if distance > creature.speed:  # Only move if not at the target
                    # Calculate direction vector
                    direction = [(creature.destination[0] - creature.position[0]) / distance,
                                (creature.destination[1] - creature.position[1]) / distance]
                    # Update position
                    creature.position[0] += direction[0] * creature.speed
                    creature.position[1] += direction[1] * creature.speed
                else:
                    if creature.quarantined == False:
                        if creature.speed == MOVE_TO_QUARANTINE_SPEED and creature.quarantined == False:
                            creature.speed = CREATURE_SPEED
                        if VERSAMMLUNGS_HOTSPOT:
                            num = random.random()
                            if num <= HOTSPOT_VISITING_CHANCE:
                                creature.destination = [random.randrange(HOTSPOT_ZONE_LEFT, HOTSPOT_ZONE_LEFT + HOTSPOT_ZONE_SIZE), random.randrange(HOTSPOT_ZONE_TOP, HOTSPOT_ZONE_TOP + HOTSPOT_ZONE_SIZE)]
                            else:
                                creature.destination = [random.randrange(int(SCREEN_WIDTH/2), SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)]
                        else:
                            creature.destination = [random.randrange(int(SCREEN_WIDTH/2), SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)]

                    elif creature.quarantined:
                        creature.speed = SPEED_IN_QUARANTINE
                        #creature.destination = [random.randrange(CHART_Y + CHART_HEIGHT + 20 + CREATURE_SIZE, CHART_Y + CHART_HEIGHT + 20 + QUARANTINE_SIZE - CREATURE_SIZE), random.randrange(CHART_Y + CREATURE_SIZE, CHART_Y + QUARANTINE_SIZE - CREATURE_SIZE)]
                        creature.destination = self.give_next_des(CHART_Y + CHART_HEIGHT + 20 + CREATURE_SIZE, CHART_Y + CHART_HEIGHT + 20 + QUARANTINE_SIZE - CREATURE_SIZE, CHART_Y + CREATURE_SIZE, CHART_Y + QUARANTINE_SIZE - CREATURE_SIZE)

    def check_distances(self):
        #Diese Funktion überprüft die Abstände zwischen kranken und gesunden Kreaturen um Infektionen festzustellen
        current_time = pygame.time.get_ticks()
        if current_time - self.last_distance_check >= DISTANCE_CHECK_TIME_MS:
            for current_creature in self.creature_list:
                if current_creature.health_status == "sick" and current_creature.quarantined == False:

                    for creature in self.creature_list:
                        if creature.health_status == "healthy":
                            distance = math.sqrt((creature.position[0] - current_creature.position[0])**2 + (creature.position[1] - current_creature.position[1])**2)
                            if distance < INFECTION_DISTANCE:
                                num = random.random()
                                if  num <= INFECTON_CHANCE: 
                                    creature.health_status = "sick"
                                    num = random.random()
                                    if self.quarantine_bool and num <= QUARANTINE_CHANCE:
                                        creature.quarantine_timer_start()
                                    creature.immune_timer_start(pygame.time.get_ticks())
                                    self.healthy_creature_amount -= 1
                                    self.sick_creature_amount += 1
                                    self.recent_infections_counter += 1
                                    new_animation = AnimationCircle(current_creature)
                                    self.infecting_animation_circles.append(new_animation)

            
            self.last_distance_check = pygame.time.get_ticks()

    def statistic_timer(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.chart_update_timer >= CHART_UPDATE_TIME:
            if self.sick_creature_amount > 0:
                self.calculate_statistic()
            else:
                self.moving_status = False
            self.chart_update_timer = pygame.time.get_ticks()

    def calculate_statistic(self):
        healthy_percentage = round(self.healthy_creature_amount/POPULATION_SIZE, 3)
        sick_percentage = round(self.sick_creature_amount/POPULATION_SIZE, 3)
        immune_percentage = 1 - healthy_percentage - sick_percentage

        if sick_percentage >= self.sick_creature_peak:
            self.sick_creature_peak = sick_percentage

        new_data = Data(healthy_percentage, sick_percentage, immune_percentage)
        self.data_set.append(new_data)
    

    def display_chart_rects(self):
        #Diese Funktion erzeugt das Live-Diagramm auf der rechten Bildschirmhälfte. Dabei werden die Anteile der 
        singe_data_width = CHART_WIDTH/len(self.data_set)
        i = 0
        for data in self.data_set:
            offset = singe_data_width
            offset *= i
            new_data_rect = pygame.Rect(CHART_X + offset, CHART_Y + CHART_HEIGHT - data.sick_length, singe_data_width + 1, data.sick_length)
            pygame.draw.rect(self.screen, SICK_CREATURE_COLOR, new_data_rect)
            new_data_rect = pygame.Rect(CHART_X + offset, CHART_Y + CHART_HEIGHT - data.sick_length - data.healthy_length, singe_data_width + 1, data.healthy_length)
            pygame.draw.rect(self.screen, HEALTHY_CREATURE_COLOR, new_data_rect)
            new_data_rect = pygame.Rect(CHART_X + offset, CHART_Y + CHART_HEIGHT - data.sick_length - data.healthy_length - data.immune_length, singe_data_width + 1, data.immune_length)
            pygame.draw.rect(self.screen, IMMUNE_CREATURE_COLOR, new_data_rect)
            i += 1
        
            if self.line_indicator_bool and data.indicator:
                pygame.draw.line(self.screen, (0,255,0), (CHART_X + offset, CHART_Y), (CHART_X + offset, CHART_Y + CHART_HEIGHT), 4)
    
    def draw_axes(self):
        #In dieser Funktion werden die Achsen des Live-Diagramms in das Fenster gezeichnet
        pygame.draw.line(self.screen, LINIEN_FARBE, (CHART_X, CHART_Y + CHART_HEIGHT), (CHART_X + CHART_WIDTH, CHART_Y + CHART_HEIGHT), 2)
        pygame.draw.line(self.screen, LINIEN_FARBE, (CHART_X, CHART_Y), (CHART_X, CHART_Y + CHART_HEIGHT), 2)

        pygame.draw.line(self.screen, LINIEN_FARBE, (CHART_X - CHART_MARK_LENGTH/2, CHART_HEIGHT/2 + 50), (CHART_X + CHART_MARK_LENGTH/2, CHART_HEIGHT/2 + 50), 2)


    def display_statistic(self):
        #Diese Funktion sorgt für die Anzeige der Statistik der Simulation
        #Also Anteil an Gesunden, Erkrankten und Genesen sowie die Reproduktionszahl, den Erkrankten Peak und die Dauer der Simulation
        text_surface = self.my_font.render(str(int(100 * self.healthy_creature_amount/POPULATION_SIZE)) + "%", False, (HEALTHY_CREATURE_COLOR))
        self.screen.blit(text_surface, (0 + CHART_X,SCREEN_HEIGHT- 160))

        text_surface = self.my_font.render(str(int(100 * self.sick_creature_amount/POPULATION_SIZE)) + "%", False, (SICK_CREATURE_COLOR))
        self.screen.blit(text_surface, (53 + CHART_X,SCREEN_HEIGHT- 160))

        text_surface = self.my_font.render(str(int(100 * self.immune_creature_amount/POPULATION_SIZE)) + "%", False, (IMMUNE_CREATURE_COLOR))
        self.screen.blit(text_surface, (98 + CHART_X,SCREEN_HEIGHT- 160))

        text_surface = self.my_font.render(f"R: {round(self.r_naught, 1)}", False, (255, 255, 255))
        self.screen.blit(text_surface, (200 + CHART_X,SCREEN_HEIGHT- 160))

        if self.moving_status:
            seconds = pygame.time.get_ticks() // 1000  
            self.seconds_running = seconds

        text = self.my_font.render(f"{self.seconds_running}s", True, (255, 255, 255))
        self.screen.blit(text, (150 + CHART_X,SCREEN_HEIGHT- 160))

        text = self.my_font.render(f"Peak: {int(self.sick_creature_peak * 100)}%", True, SICK_CREATURE_COLOR)
        self.screen.blit(text, (300 + CHART_X,SCREEN_HEIGHT- 160))

    
    def add_creature(self, health, position):
        #Diese Funktion je nach Eingabe eine gesunde, erkrankte oder genesene Kreatur in das Fenster
        new_creature = Creature(health, self, len(self.creature_list) + 1)
        new_creature.position = position
        if health == "sick":
            new_creature.immune_timer_start(HEALING_DURATION)
            self.sick_creature_amount += 1
        elif health == "healthy":
            self.healthy_creature_amount += 1
        elif health == "immune":
            self.immune_creature_amount += 1

        self.creature_list.append(new_creature)


    def spawn_creatures(self):
        #Diese Funktion setzt zu Beginn des Programms alle Kreaturen an zufälligen Positionen in das Fenster
        healthy_amount = int(POPULATION_SIZE * (1 - INFECTED_PERCENTAGE_AT_START))
        infected_amount = int(POPULATION_SIZE - healthy_amount)
        for i in range(healthy_amount):
            creature = Creature("healthy", self, len(self.creature_list) + 1)
            self.creature_list.append(creature)
            self.healthy_creature_amount += 1

        for i in range(infected_amount):
            creature = Creature("sick", self, len(self.creature_list) + 1)
            creature.immune_timer_start(pygame.time.get_ticks())
            if self.quarantine_bool and random.random() <= QUARANTINE_CHANCE:
                creature.quarantine_timer_start()
            self.creature_list.append(creature)
            self.sick_creature_amount += 1


    def shutdown(self):
        #Diese Funktionen stoppt die Simulationen und schließt das Fenster
        for creature in self.creature_list:
            creature.timer.cancel()
            creature.quarantine_timer.cancel()
        
        if SAVE_DATA:
            save_data.save_data(self.data_set)
        sys.exit()

    def infecting_animation(self):
        #Diese Funktion erzeugt eine Animation bei Infizierung einer Kreatur
        for animation in self.infecting_animation_circles:
            if animation.growing == True:
                animation.radius += CIRCLE_GROWTH_RATE
                if animation.radius >= CIRCLE_MAX_RADIUS:
                    animation.growing = False
            else:
                animation.radius -= CIRCLE_GROWTH_RATE
                if animation.radius <= CIRCLE_MIN_RADIUS:
                    self.infecting_animation_circles.remove(animation)

            pygame.draw.circle(self.screen, INFECTING_ANIMATION_COLOR, animation.position, animation.radius, 2)    
    
    def check_game_over(self):
        #Diese Funktion führt stoppt die Simulation nach 3 Sekunden
        if self.shuting_down:
            if pygame.time.get_ticks() >= self.shut_down_timer + 3:
                self.shutdown()
        if self.sick_creature_amount == 0:
            self.shuting_down = True
            self.shut_down_timer = pygame.time.get_ticks()

    def quarantäne(self):
        #Diese Funktion zeichnet die Quarantäneregion in das Fenster
        q_zone = pygame.Rect(CHART_Y + CHART_HEIGHT + 20, CHART_Y, QUARANTINE_SIZE, QUARANTINE_SIZE)
        pygame.draw.rect(self.screen, LINIEN_FARBE, q_zone, 2)


    def give_next_des(self, min_x, max_x, min_y, max_y):
        #Diese Funktion generiert eine zufällige Position innerhalb einer gegebenen Region
        destination = [random.randrange(min_x, max_x), random.randrange(min_y, max_y)]
        return destination
       
    def draw_hotspot_zone(self):
        #Diese Funktion zeichnet die Zone des Versammlungshotspots in das Fenster
        hotspot_zone = pygame.Rect(HOTSPOT_ZONE_LEFT, HOTSPOT_ZONE_TOP, HOTSPOT_ZONE_SIZE, HOTSPOT_ZONE_SIZE)
        pygame.draw.rect(self.screen, LINIEN_FARBE, hotspot_zone, 2)

    def calculate_r_naught(self):
        #In dieser Funktion wird die Reprodukionszahl berrechnet
        if self.active_infected > 0:
            self.r_naught = self.recent_infections_counter/self.active_infected
        else:
            self.r_naught = 0

    def update_r_naught(self):
        #In dieser Funktion wird die Reproduktionszahl aktualisiert
        current_time = pygame.time.get_ticks()
        if current_time - self.last_r_update >= R_UPDATE_INTERVALL:
            self.calculate_r_naught()
            self.recent_infections_counter = 0
            self.active_infected = self.sick_creature_amount
            self.zeit_vergangen = 0
            self.last_r_update = pygame.time.get_ticks()
        

class Creature:
    #Dies ist die Klasse für die Kreaturen
    def __init__(self, health, game, id):
        self.health_status = health
        self.position = [random.randrange(int(SCREEN_WIDTH//2), SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)]
        self.destination = [random.randrange(int(SCREEN_WIDTH//2), SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)]
        self.count = HEALING_DURATION
        self.game = game
        self.speed = CREATURE_SPEED
        self.timer = threading.Timer(HEALING_DURATION, self.immune_creature)
        self.quarantine_timer = threading.Timer(TIME_TO_QUARANTINE, self.quarantine_creature)
        self.quarantined = False

        self.creature_id = id

    def quarantine_timer_start(self):
        self.quarantine_timer.start()

    def immune_timer_start(self, start_time):
        self.timer.start()

    def immune_creature(self):
        self.health_status = "immune"
        self.game.immune_creature_amount += 1
        self.game.sick_creature_amount -= 1
        if self.quarantined == True:
            self.dequarantine_creature()
    
    def dequarantine_creature(self):
        self.quarantined = False
        self.speed = MOVE_TO_QUARANTINE_SPEED
        self.destination = [random.randrange(int(SCREEN_WIDTH/2), SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)]
        

    def quarantine_creature(self):
        self.quarantined = True
        self.destination = [random.randrange(CHART_Y + CHART_HEIGHT + 20 + CREATURE_SIZE, CHART_Y + CHART_HEIGHT + 20 + QUARANTINE_SIZE - CREATURE_SIZE), random.randrange(CHART_Y + CREATURE_SIZE, CHART_Y + QUARANTINE_SIZE - CREATURE_SIZE)]
        self.speed = MOVE_TO_QUARANTINE_SPEED


class AnimationCircle:
    #Dies ist eine Klasse für die Infiezierugnsanimation
    def __init__(self, creature):
        self.position = creature.position
        self.radius = CIRCLE_MIN_RADIUS
        self.growing = True

class Data:
    #Dies ist eine Klasse für einen Datensatz im Live-Diagramm
    def __init__(self, healthy, sick, immune):
        self.healthy_length = CHART_HEIGHT * healthy
        self.sick_length = CHART_HEIGHT * sick
        self.immune_length = CHART_HEIGHT * immune
        self.indicator = False



sim = Simulation()
sim.run_simulation()