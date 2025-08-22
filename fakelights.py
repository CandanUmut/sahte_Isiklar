# Işık Bahçesi — "Sahte Işıklar vs. Hakiki Nur" Görsel Simülasyon (Pygame tek dosya)
# -----------------------------------------------------------------------------
# Dinamik ve anlaşılır orbit sürümü v3:
#  - Ajanlar **her yere yayılıyor**, hedef değiştirme daha kolay (0.6–1.8 sn) + merak/keşif (epsilon-greedy).
#  - **Gerçek Işık dışında kalan ajanlar** zamanla **kararıyor** (baz ışıkta ambient sönüm),
#    Gerçek Işık ringine gelince **yeniden aydınlanıyor** (baz yükselir, afterglow).
#  - Orbit net: her kaynak çevresinde ring hedefine takip; merkez/kenar takılmaları yok.
#  - Gerçek Işık kaynağına toplu temas oldukça **global parlaklık** artar, yavaş sönümlenir.
#  - Bildirim güncellemesi güvenli (IndexError fix).
# -----------------------------------------------------------------------------
# Çalıştırma:
#   pip install pygame
#   python isik_bahcesi_simulasyon.py
# -----------------------------------------------------------------------------

import math
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional

import pygame
from bisect import bisect_left

# --- Pencere ayarları --------------------------------------------------------
WIDTH, HEIGHT = 800, 1000
FPS = 60
TITLE = "Işık Bahçesi — Sahte Işıklar vs. Hakiki Nur"

# --- Renkler -----------------------------------------------------------------
BLACK = (10, 12, 18)
WHITE = (240, 240, 240)
GRAY = (120, 130, 140)
SOFT_GRAY = (80, 88, 96)

NEON_BLUE = (50, 200, 255)       # Sosyal medya
NEON_PINK = (255, 80, 200)       # Pornografi
NEON_PURPLE = (180, 120, 255)    # Tüketim/Şöhret
NEON_RED = (255, 90, 90)         # Alkol/Uyuşturucu

AMBER = (255, 196, 77)           # Gerçek Işık (sıcak)
GOLD = (248, 220, 120)
HEALTH_GREEN = (95, 220, 120)
CYAN = (80, 220, 220)
PANEL_BG = (20, 24, 32)
PANEL_LINE = (48, 54, 66)

# --- Simülasyon sabitleri ----------------------------------------------------
AGENT_COUNT = 200
AGENT_RADIUS = 5
SOURCE_RADIUS = 24            # çekirdek daire
ORBIT_BAND = 28               # çekirdekten şu kadar ötede ring hedefi
ORBIT_BW = 12                 # ring kalınlığı (etkileşim bandı)

SOCIAL = "SOSYAL"
SUBSTANCE = "MADDE"
PORN = "PORNO"
CONSUME = "TUKETIM"
REAL = "GERCEK"
ALL_TYPES = [SOCIAL, SUBSTANCE, PORN, CONSUME, REAL]

# Preset anahtarları (toggle)
PRESET_KEYS = {
    pygame.K_b: "Bildirim Fırtınası",
    pygame.K_o: "Dijital Oruç",
    pygame.K_r: "Ramazan Etkisi",
    pygame.K_g: "Destek Grubu",
    pygame.K_f: "Filtre Açık",
}

# --- Yardımcı ---------------------------------------------------------------
def clamp(v, a, b):
    return max(a, min(b, v))

def mix(c1, c2, t):
    t = clamp(t, 0, 1)
    return (int(c1[0] + (c2[0]-c1[0])*t),
            int(c1[1] + (c2[1]-c1[1])*t),
            int(c1[2] + (c2[2]-c1[2])*t))

# --- Basit sıralı indeks -----------------------------------------------------
class BTreeIndex:
    def __init__(self):
        self.keys: List[float] = []
        self.ids: List[int] = []
    def insert(self, key: float, id_: int):
        i = bisect_left(self.keys, key)
        self.keys.insert(i, key); self.ids.insert(i, id_)

# --- Rule/Relational ---------------------------------------------------------
@dataclass
class RuleEngine:
    affinity: Dict[Tuple[int, str], float] = field(default_factory=dict)
    orbit_base: Dict[str, float] = field(default_factory=dict)
    def build(self, n: int):
        self.orbit_base = {
            SOCIAL: SOURCE_RADIUS + ORBIT_BAND + 4,
            SUBSTANCE: SOURCE_RADIUS + ORBIT_BAND + 8,
            PORN: SOURCE_RADIUS + ORBIT_BAND + 6,
            CONSUME: SOURCE_RADIUS + ORBIT_BAND + 10,
            REAL: SOURCE_RADIUS + ORBIT_BAND + 18,
        }
        for i in range(n):
            self.affinity[(i, SOCIAL)] = clamp(random.gauss(0.25, 0.12), 0.0, 1.0)
            self.affinity[(i, SUBSTANCE)] = clamp(random.gauss(0.06, 0.06), 0.0, 0.5)
            self.affinity[(i, PORN)] = clamp(random.gauss(0.14, 0.08), 0.0, 0.7)
            self.affinity[(i, CONSUME)] = clamp(random.gauss(0.18, 0.10), 0.0, 0.8)
            self.affinity[(i, REAL)] = clamp(random.gauss(0.20, 0.12), 0.0, 1.0)

RULES = RuleEngine()

# --- Veri sınıfları ----------------------------------------------------------
@dataclass
class Source:
    type: str
    pos: pygame.Vector2
    color: Tuple[int, int, int]
    label: str
    pulse: float = 0.0

    def draw(self, surf: pygame.Surface, font_small, real_intensity: float = 0.0):
        # Glow katmanları
        self.pulse = (self.pulse + 0.03) % (2*math.pi)
        pr = SOURCE_RADIUS + 3*math.sin(self.pulse*2)
        base_col = self.color
        if self.type == REAL:
            # Gerçek ışık gitgide parlaklaşsın
            t = clamp(0.3 + 0.7*real_intensity, 0.3, 1.0)
            base_col = mix(self.color, WHITE, 0.4*t)
        for r, a in ((int(pr)+20, 30), (int(pr)+10, 50), (int(pr), 80)):
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*base_col, a), (r, r), r)
            surf.blit(s, (self.pos.x-r, self.pos.y-r))
        pygame.draw.circle(surf, base_col, self.pos, SOURCE_RADIUS)
        # Orbit halkası
        orbit_r = RULES.orbit_base[self.type]
        pygame.draw.circle(surf, mix(base_col, WHITE, 0.3), self.pos, int(orbit_r), 1)
        pygame.draw.circle(surf, mix(base_col, WHITE, 0.12), self.pos, int(orbit_r+ORBIT_BW), 1)
        # Etiket
        label_surf = font_small.render(self.label, True, WHITE)
        surf.blit(label_surf, (self.pos.x - label_surf.get_width()/2, self.pos.y - SOURCE_RADIUS - 18))

@dataclass
class Agent:
    id: int
    pos: pygame.Vector2
    vel: pygame.Vector2
    inner_light: float = 55.0
    base_light: float = 50.0
    willpower: float = 0.35
    health: float = 1.0
    social_ties: float = 0.5
    cravings: Dict[str, float] = field(default_factory=lambda: {
        SOCIAL: 0.25, SUBSTANCE: 0.08, PORN: 0.15, CONSUME: 0.20, REAL: 0.10,
    })
    desens: float = 0.0
    hedonic: float = 0.0
    pending_crash: float = 0.0
    last_stimulus: Optional[str] = None
    last_contact_timer: float = 0.0
    selected: bool = False

    # Orbit ve keşif parametreleri
    target_type: str = REAL
    theta: float = field(default_factory=lambda: random.uniform(0, 2*math.pi))
    omega: float = field(default_factory=lambda: random.uniform(0.6, 1.6))  # rad/sn
    orbit_jitter: float = field(default_factory=lambda: random.uniform(-6.0, 6.0))
    next_retarget: float = 0.0
    stay_time: float = 0.0
    curiosity: float = 0.0
    epsilon: float = field(default_factory=lambda: random.uniform(0.08, 0.22))  # keşif olasılığı
    time_since_real: float = 10.0  # gerçek ışıktan uzak kalma süresi (sn)

    def retarget(self, sources: List['Source'], globals):
        if self.next_retarget > 0:
            return
        self.next_retarget = random.uniform(0.6, 1.8)  # daha dinamik
        self.stay_time += self.next_retarget
        self.curiosity = clamp(self.curiosity + 0.12*self.next_retarget, 0, 1)

        # Keşif (epsilon-greedy + merak)
        if random.random() < self.epsilon*(0.6 + 0.8*self.curiosity):
            choice = random.choice(sources)
            self._apply_target(choice)
            return

        # Skor bazlı seçim
        best = None; best_score = -1e9
        for s in sources:
            dist = (self.pos - s.pos).length() + 1e-3
            near = 1.0/(0.02*dist + 1.0)
            aff = RULES.affinity[(self.id, s.type)]
            crave = self.cravings.get(s.type, 0.0)
            mult = 1.0
            if s.type == SOCIAL:
                if globals['digital_oruc']: mult *= 0.35
                if globals['bildirim_firtinasi']: mult *= 1.35
            if s.type == PORN and globals['filtre_acik']: mult *= 0.4
            if s.type in (SUBSTANCE, PORN, CONSUME): mult *= (1.0 - 0.6*self.willpower)
            if s.type == REAL:
                mult *= (1.0 + 0.6*self.willpower + 0.25*self.social_ties)
                if globals['ramazan']: mult *= 1.3
            if s.type == PORN: mult *= (1.0 - 0.5*self.desens)
            if s.type == CONSUME: mult *= (1.0 - 0.5*self.hedonic)
            # aynı hedefte uzun kalmanın verdiği sıkılma
            mono = 0.85 if self.last_stimulus == s.type else 1.0
            score = (0.9*near + 1.2*aff + 1.2*crave) * mult * mono
            if score > best_score: best_score, best = score, s
        if best:
            self._apply_target(best)

    def _apply_target(self, s: 'Source'):
        self.target_type = s.type
        # yeni hedefe geçerken açı ve hız uyarlaması
        self.theta = math.atan2(self.pos.y - s.pos.y, self.pos.x - s.pos.x)
        self.omega = random.uniform(0.7, 1.4) * random.choice([-1, 1])
        # merak ve kalış süresi sıfırla (değişimi tetikledik)
        self.curiosity *= 0.4
        self.stay_time = 0.0

    def move_orbit(self, src: 'Source', dt: float):
        r0 = RULES.orbit_base[src.type] + self.orbit_jitter
        self.theta += self.omega * dt
        # küçük kaotik dalga: daha organik halka hareketi
        wob = 4.0 * math.sin(self.theta*0.6 + 0.7*self.id)
        pos_des = pygame.Vector2(
            src.pos.x + math.cos(self.theta) * (r0 + wob),
            src.pos.y + math.sin(self.theta) * (r0 + wob),
        )
        k = 0.16 if (self.pos - pos_des).length() < 80 else 0.24
        self.pos += (pos_des - self.pos) * k
        self.pos.x = clamp(self.pos.x, 40, WIDTH-300-40)
        self.pos.y = clamp(self.pos.y, 40, HEIGHT-40)

    def natural_dynamics(self, dt: float):
        # İç ışık bazına doğru sönme
        self.inner_light += (self.base_light - self.inner_light) * (0.8*dt)
        if self.pending_crash > 0:
            pay = min(self.pending_crash, 0.25)
            self.pending_crash -= pay
            self.inner_light -= pay
        # Gerçek ışıktan uzak kalma → ambient sönüm
        self.time_since_real += dt
        if self.target_type != REAL and self.time_since_real > 0.6:
            self.base_light -= 0.18 * dt  # kararma hızı
        self.inner_light = clamp(self.inner_light, 0, 100)
        self.base_light = clamp(self.base_light, 5, 100)
        self.health = clamp(self.health, 0, 1)
        self.social_ties = clamp(self.social_ties, 0, 1)
        for k in self.cravings:
            self.cravings[k] = clamp(self.cravings[k], 0, 1.2)

        # >>> EKLENDİ: Gerçek Işık hedefi değilse iç ışık zamanla sönsün
        if self.target_type != REAL:
            self.inner_light -= 5.0 * dt  # sn başına ~5 puan düşüş
        # <<<

        self.desens = clamp(self.desens, 0, 1)
        self.hedonic = clamp(self.hedonic, 0, 1)
        self.willpower = clamp(self.willpower, 0, 1)
        if self.last_contact_timer > 0: self.last_contact_timer -= dt
        else: self.last_stimulus = None
        if self.next_retarget > 0: self.next_retarget -= dt

    def contact_if_on_ring(self, src: 'Source', local_density: float, globals):
        dist = (self.pos - src.pos).length()
        r = RULES.orbit_base[src.type]
        if abs(dist - r) <= ORBIT_BW:
            # >>> EKLENDİ: Etkiyi 0.6 sn’de bir uygula
            if self.last_contact_timer > 0:
                self.last_stimulus = src.type  # sadece etiket güncel kalsın
                return
            self.last_contact_timer = 0.6
            # <<<
            self.last_stimulus = src.type
            dens_pen = 1.0 / (1.0 + 1.2*local_density)
            if src.type == SOCIAL:
                spike = 2.2; crash = 2.2
                self.inner_light += spike; self.pending_crash += crash
                self.cravings[SOCIAL] += 0.03; self.base_light -= 0.18 * dens_pen
            elif src.type == SUBSTANCE:
                spike = 9.5; crash = 9.5
                self.inner_light += spike; self.pending_crash += crash
                self.health -= 0.12; self.cravings[SUBSTANCE] += 0.07
                self.willpower -= 0.05; self.base_light -= 0.65 * dens_pen
            elif src.type == PORN:
                spike = 5.0; crash = 4.8
                self.inner_light += spike; self.pending_crash += crash
                self.desens += 0.05; self.cravings[PORN] += 0.05
                self.social_ties -= 0.04; self.base_light -= 0.34 * dens_pen
            elif src.type == CONSUME:
                spike = 5.6*(1.0-0.5*self.hedonic); crash = 5.2
                self.inner_light += spike; self.pending_crash += crash
                self.hedonic += 0.05; self.cravings[CONSUME] += 0.05
                self.base_light -= 0.28 * dens_pen
            elif src.type == REAL:
                saturation = 0.45 + 0.55*(1.0 - self.base_light/100.0)
                gain = 0.8 * saturation * dens_pen
                self.base_light += gain; self.inner_light += 0.6 * saturation
                self.pending_crash = max(0.0, self.pending_crash - 0.9)
                self.willpower += 0.03; self.social_ties += 0.025; self.health += 0.02
                self.cravings[SOCIAL] -= 0.011; self.cravings[PORN] -= 0.017
                self.cravings[CONSUME] -= 0.017; self.cravings[SUBSTANCE] -= 0.02
                self.time_since_real = 0.0  # aydınlanma → kararma sayacı sıfır

    def color(self):
        t = self.inner_light / 100.0
        base = mix(SOFT_GRAY, WHITE, t)
        if self.last_stimulus == REAL: tint = AMBER
        elif self.last_stimulus == SOCIAL: tint = NEON_BLUE
        elif self.last_stimulus == PORN: tint = NEON_PINK
        elif self.last_stimulus == CONSUME: tint = NEON_PURPLE
        elif self.last_stimulus == SUBSTANCE: tint = NEON_RED
        else: tint = mix(base, HEALTH_GREEN, 0.15*(1.0 - self.health))
        return mix(base, tint, 0.55)

    def draw(self, surf: pygame.Surface):
        c = self.color()
        for r, a in ((AGENT_RADIUS+7, 30), (AGENT_RADIUS+3, 60)):
            glow = (*c[:3], a)
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, glow, (r, r), r)
            surf.blit(s, (self.pos.x-r, self.pos.y-r))
        pygame.draw.circle(surf, c, (int(self.pos.x), int(self.pos.y)), AGENT_RADIUS)
        if self.selected:
            pygame.draw.circle(surf, GOLD, (int(self.pos.x), int(self.pos.y)), AGENT_RADIUS+2, 1)

# --- Başlat ------------------------------------------------------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()

font = pygame.font.SysFont("Verdana", 18)
font_small = pygame.font.SysFont("Verdana", 14)

# --- Kaynaklar ---------------------------------------------------------------
margin = 90
cx = (WIDTH-300)//2
cy = HEIGHT//2
sources: List[Source] = [
    Source(SOCIAL, pygame.Vector2(margin, margin), NEON_BLUE, "Sosyal Medya"),
    Source(SUBSTANCE, pygame.Vector2(WIDTH-300-margin, margin), NEON_RED, "Alkol/Uyuşturucu"),
    Source(PORN, pygame.Vector2(margin, HEIGHT-margin), NEON_PINK, "Pornografi"),
    Source(CONSUME, pygame.Vector2(WIDTH-300-margin, HEIGHT-margin), NEON_PURPLE, "Tüketim/Şöhret"),
    Source(REAL, pygame.Vector2(cx, cy), AMBER, "Gerçek Işık"),
]

# --- Ajan/İlişki önhazırlığı -------------------------------------------------
RULES.build(AGENT_COUNT)

agents: List[Agent] = []
for i in range(AGENT_COUNT):
    x = random.uniform(60, WIDTH-300-60)
    y = random.uniform(60, HEIGHT-60)
    a = Agent(i, pygame.Vector2(x, y), pygame.Vector2(0, 0))
    a.willpower = clamp(random.gauss(0.4, 0.18), 0, 1)
    a.social_ties = clamp(random.gauss(0.55, 0.2), 0, 1)
    a.base_light = clamp(random.gauss(52, 10), 0, 100)
    a.inner_light = clamp(a.base_light + random.uniform(-5, 5), 0, 100)
    a.target_type = random.choice(ALL_TYPES)  # başta tüm alana yayılma
    agents.append(a)

# --- Global durum / presetler ------------------------------------------------
globals_state = {
    'bildirim_firtinasi': False,
    'digital_oruc': False,
    'ramazan': False,
    'destek_grubu': False,
    'filtre_acik': False,
    'paused': False,
}

notifications: List[Tuple[str, float]] = []
real_intensity = 0.0  # Gerçek Işık küresel parlaklık katsayısı (0..1)

# --- UI yardımcıları ---------------------------------------------------------
def push_note(msg: str, sec: float = 2.5):
    notifications.append((msg, sec))


def update_notifications(dt: float):
    global notifications
    notifications = [(m, t-dt) for (m, t) in notifications if t-dt > 0]


def draw_notifications(surf: pygame.Surface):
    y = 12
    for (msg, t) in notifications:
        alpha = 255 if t > 0.5 else int(255 * (t/0.5))
        text = font_small.render(msg, True, WHITE)
        box = pygame.Surface((text.get_width()+12, text.get_height()+8), pygame.SRCALPHA)
        pygame.draw.rect(box, (30, 36, 48, alpha), box.get_rect(), border_radius=8)
        box.blit(text, (6, 4))
        screen.blit(box, (12, y))
        y += text.get_height() + 10


def draw_panel(surf: pygame.Surface, agents: List[Agent]):
    panel = pygame.Rect(WIDTH-300, 0, 300, HEIGHT)
    pygame.draw.rect(surf, PANEL_BG, panel)
    pygame.draw.line(surf, PANEL_LINE, (WIDTH-300, 0), (WIDTH-300, HEIGHT), 1)

    if agents:
        avg_inner = sum(a.inner_light for a in agents) / len(agents)
        avg_health = sum(a.health for a in agents) / len(agents)
        avg_ties = sum(a.social_ties for a in agents) / len(agents)
        avg_des = sum(a.desens for a in agents) / len(agents)
        avg_hed = sum(a.hedonic for a in agents) / len(agents)
        loneliness = 1.0 - avg_ties
    else:
        avg_inner = avg_health = avg_ties = avg_des = avg_hed = loneliness = 0

    def bar(y, label, val, color):
        pygame.draw.rect(surf, SOFT_GRAY, (WIDTH-280, y, 240, 18), border_radius=6)
        pygame.draw.rect(surf, color, (WIDTH-280, y, int(240*clamp(val,0,1)), 18), border_radius=6)
        text = font_small.render(label, True, WHITE)
        surf.blit(text, (WIDTH-280, y-18))

    title = font.render("METRİKLER", True, WHITE)
    surf.blit(title, (WIDTH-300 + (300-title.get_width())//2, 12))

    base_y = 54
    bar(base_y+0*44, "İç Işık (ort)", avg_inner/100.0, AMBER)
    bar(base_y+1*44, "Yalnızlık Endeksi", loneliness, NEON_BLUE)
    bar(base_y+2*44, "Sağlık", avg_health, HEALTH_GREEN)
    bar(base_y+3*44, "Desensitizasyon", avg_des, NEON_PINK)
    bar(base_y+4*44, "Hedonik Adaptasyon", avg_hed, NEON_PURPLE)

    y2 = base_y + 5*44 + 24
    surf.blit(font.render("KAYNAKLAR", True, WHITE), (WIDTH-280, y2))
    y2 += 30
    legend = [
        (NEON_BLUE, "Sosyal Medya"), (NEON_RED, "Alkol/Uyuşturucu"), (NEON_PINK, "Pornografi"),
        (NEON_PURPLE, "Tüketim/Şöhret"), (AMBER, "Gerçek Işık"),
    ]
    for c, name in legend:
        pygame.draw.circle(surf, c, (WIDTH-280+10, y2+8), 7)
        surf.blit(font_small.render(name, True, WHITE), (WIDTH-280+24, y2))
        y2 += 24

    y3 = y2 + 10
    surf.blit(font.render("KONTROLLER", True, WHITE), (WIDTH-280, y3))
    y3 += 30
    lines = [
        "B: Bildirim Fırtınası", "O: Dijital Oruç", "R: Ramazan Etkisi", "G: Destek Grubu",
        "F: Filtre Açık", "Space: Duraklat", "Tık: Ajan seç",
    ]
    for ln in lines:
        surf.blit(font_small.render(ln, True, GRAY), (WIDTH-280, y3)); y3 += 20


def draw_agent_info(surf: pygame.Surface, agent: Agent):
    if not agent:
        return

    # Boyutlar
    BOX_W, BOX_H = 210, 220
    box = pygame.Surface((BOX_W, BOX_H), pygame.SRCALPHA)
    pygame.draw.rect(box, (28, 34, 46, 230), (0, 0, BOX_W, BOX_H), border_radius=12)
    pygame.draw.rect(box, (60, 70, 86, 255), (0, 0, BOX_W, BOX_H), 1, border_radius=12)

    def ln(y, label, val, fmt="{:.2f}"):
        surf_lbl = font_small.render(label, True, WHITE)
        val_str = font_small.render(fmt.format(val), True, GOLD)
        box.blit(surf_lbl, (12, y))
        box.blit(val_str, (170, y))

    ln(10,  "İç Işık", agent.inner_light, "{:.1f}")
    ln(32,  "Baz Işık", agent.base_light, "{:.1f}")
    ln(54,  "Sağlık", agent.health)
    ln(76,  "İrade", agent.willpower)
    ln(98,  "Sosyal Bağ", agent.social_ties)
    ln(120, "Desens.", agent.desens)
    ln(142, "Hedonik", agent.hedonic)
    ln(164, "Keşif ε", agent.epsilon)

    lbl = font_small.render(f"Hedef: {agent.target_type}", True, CYAN)
    box.blit(lbl, (12, 184))
    lbl2 = font_small.render(f"Son Uyarı: {agent.last_stimulus or '-'}", True, CYAN)
    box.blit(lbl2, (12, 202))

    # --- Alt-orta konumlandırma ---
    # Sağdaki 300px paneli hariç tutup, oyun alanının ortasını hesapla
    play_w = WIDTH - 300
    x = int((play_w - BOX_W) / 2)
    y = HEIGHT - BOX_H - 20  # alttan 20px boşluk
    surf.blit(box, (x, y))


# --- Ana döngü ---------------------------------------------------------------
selected_agent: Optional[Agent] = None

while True:
    dt = clock.tick(FPS) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                globals_state['paused'] = not globals_state['paused']
                push_note("Duraklatıldı" if globals_state['paused'] else "Devam")
            if event.key in PRESET_KEYS:
                name = PRESET_KEYS[event.key]
                if event.key == pygame.K_b: globals_state['bildirim_firtinasi'] = not globals_state['bildirim_firtinasi']
                elif event.key == pygame.K_o: globals_state['digital_oruc'] = not globals_state['digital_oruc']
                elif event.key == pygame.K_r: globals_state['ramazan'] = not globals_state['ramazan']
                elif event.key == pygame.K_g: globals_state['destek_grubu'] = not globals_state['destek_grubu']
                elif event.key == pygame.K_f: globals_state['filtre_acik'] = not globals_state['filtre_acik']
                state = []
                if globals_state['bildirim_firtinasi']: state.append('Bildirim')
                if globals_state['digital_oruc']: state.append('Oruç')
                if globals_state['ramazan']: state.append('Ramazan')
                if globals_state['destek_grubu']: state.append('Destek')
                if globals_state['filtre_acik']: state.append('Filtre')
                push_note(f"Aktif: {', '.join(state) if state else 'Yok'}")
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < WIDTH-300:
                best = None; best_d = 9999
                for a in agents:
                    d = math.hypot(a.pos.x-mx, a.pos.y-my)
                    if d < best_d and d < 18: best = a; best_d = d
                if best:
                    if selected_agent: selected_agent.selected = False
                    selected_agent = best; selected_agent.selected = True

    if not globals_state['paused']:
        update_notifications(dt)

        # Yoğunluk ölçümü
        density = {t: 0 for t in ALL_TYPES}
        for a in agents:
            a.retarget(sources, globals_state)
            tgt = next(s for s in sources if s.type == a.target_type)
            a.move_orbit(tgt, dt)
            r = RULES.orbit_base[tgt.type]
            if abs((a.pos - tgt.pos).length() - r) <= ORBIT_BW: density[tgt.type] += 1
        for k in density: density[k] = density[k] / max(1, AGENT_COUNT/5)

        # Etkileşim & dinamikler
        real_count = 0
        for a in agents:
            tgt = next(s for s in sources if s.type == a.target_type)
            a.contact_if_on_ring(tgt, density[tgt.type], globals_state)
            a.natural_dynamics(dt)
            if tgt.type == REAL and abs((a.pos - tgt.pos).length() - RULES.orbit_base[REAL]) <= ORBIT_BW:
                real_count += 1
        # Gerçek ışık parlaklığı
        real_intensity += 0.0025 * real_count
        real_intensity *= 0.997
        real_intensity = clamp(real_intensity, 0.0, 1.0)

    # Çizim
    screen.fill(BLACK)
    for s in sources:
        s.draw(screen, font_small, real_intensity if s.type == REAL else 0.0)
    for a in agents: a.draw(screen)
    draw_panel(screen, agents)
    draw_notifications(screen)
    if selected_agent: draw_agent_info(screen, selected_agent)

    header = font.render("Işık Bahçesi — Sahte Işıklar vs. Hakiki Nur", True, WHITE)
    screen.blit(header, (18, 10))
    sub = font_small.render("B:Bildirim  O:Oruç  R:Ramazan  G:Destek  F:Filtre  Space:Duraklat  Tık:Seç", True, GRAY)
    screen.blit(sub, (18, 36))

    pygame.display.flip()
