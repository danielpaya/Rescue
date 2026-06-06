import math

from rescue_pc_brain import control_config as cfg


class GearboxManager:
    def __init__(self):
        self.current_gear = cfg.DEFAULT_GEAR
        self.direction = cfg.DEFAULT_DIRECTION

        self.last_triangle_state = 0
        self.last_circle_state = 0
        self.last_x_state = 0

    def get_gear_limit(self):
        return cfg.GEAR_LIMITS[self.current_gear]

    def shift_up(self):
        if self.current_gear < cfg.MAX_GEAR:
            self.current_gear += 1

    def shift_down(self):
        if self.current_gear > cfg.MIN_GEAR:
            self.current_gear -= 1

    def can_toggle_direction(self, real_speed_abs):
        return real_speed_abs <= cfg.REAL_SPEED_ZERO_THRESHOLD

    def toggle_direction(self):
        if self.direction == cfg.DIRECTION_FORWARD:
            self.direction = cfg.DIRECTION_REVERSE
        else:
            self.direction = cfg.DIRECTION_FORWARD

    def direction_sign(self):
        if self.direction == cfg.DIRECTION_FORWARD:
            return 1.0

        return -1.0

    def handle_manual_buttons(self, controller_state, real_speed_abs):
        """
        L1 + Triángulo = subir caja manualmente
        L1 + Círculo   = bajar caja manualmente
        L1 + X         = cambiar FORWARD/REVERSE solo si la velocidad real está en cero

        L2 queda libre para freno progresivo.
        """

        l1_active = controller_state.l1_pressed == 1

        triangle_pressed = controller_state.triangle_pressed
        circle_pressed = controller_state.circle_pressed
        x_pressed = controller_state.x_pressed

        if l1_active:
            # Subida manual de caja
            if triangle_pressed == 1 and self.last_triangle_state == 0:
                self.shift_up()

            # Bajada manual de caja
            if circle_pressed == 1 and self.last_circle_state == 0:
                self.shift_down()

            # Cambio FORWARD / REVERSE
            if x_pressed == 1 and self.last_x_state == 0:
                if self.can_toggle_direction(real_speed_abs):
                    self.toggle_direction()

        self.last_triangle_state = triangle_pressed
        self.last_circle_state = circle_pressed
        self.last_x_state = x_pressed

    def get_command_intensity(self, controller_state):
        """
        Calcula si el operador está pidiendo movimiento.

        Usa:
            magnitud del joystick * R2
        """

        joystick_x = controller_state.joystick_x
        joystick_y = controller_state.joystick_y

        joystick_magnitude = math.sqrt(
            joystick_x ** 2 +
            joystick_y ** 2
        )

        if joystick_magnitude > 1.0:
            joystick_magnitude = 1.0

        return joystick_magnitude * controller_state.r2_value

    def gear_from_real_speed(self, real_speed_abs):
        """
        Convierte velocidad real normalizada en caja.

        Caja 1: 0.00 - 0.20
        Caja 2: 0.20 - 0.40
        Caja 3: 0.40 - 0.60
        Caja 4: 0.60 - 0.80
        Caja 5: 0.80 - 1.00
        """

        if real_speed_abs >= 0.80:
            return 5

        if real_speed_abs >= 0.60:
            return 4

        if real_speed_abs >= 0.40:
            return 3

        if real_speed_abs >= 0.20:
            return 2

        return 1

    def sync_gear_with_real_speed(self, controller_state, real_speed_abs):
        """
        Baja automáticamente la caja según la velocidad real.

        Reglas:
        - La caja puede bajar sola.
        - La caja NO puede subir sola.
        - La caja también puede bajar manualmente con L1 + Círculo.
        - La caja sube únicamente con L1 + Triángulo.
        """

        l1_active = controller_state.l1_pressed == 1
        circle_pressed = controller_state.circle_pressed == 1

        # Círculo solo = freno normal.
        # L1 + Círculo = bajar caja manualmente.
        brake_active = circle_pressed and not l1_active

        command_intensity = self.get_command_intensity(controller_state)

        operator_requesting_motion = (
            command_intensity > cfg.GEAR_SYNC_COMMAND_THRESHOLD
        )

        # Si el operador está acelerando y no está frenando,
        # no sincronizamos hacia abajo.
        # Esto evita que al intentar acelerar se baje la caja sola.
        if operator_requesting_motion and not brake_active:
            return

        real_gear = self.gear_from_real_speed(real_speed_abs)

        # Solo baja automáticamente.
        # Nunca sube automáticamente.
        if real_gear < self.current_gear:
            self.current_gear = real_gear

    def update(self, controller_state, real_speed_abs):
        """
        Actualiza:
        - Cambios manuales
        - FORWARD / REVERSE
        - Bajada automática según velocidad real
        """

        self.handle_manual_buttons(
            controller_state,
            real_speed_abs
        )

        self.sync_gear_with_real_speed(
            controller_state,
            real_speed_abs
        )