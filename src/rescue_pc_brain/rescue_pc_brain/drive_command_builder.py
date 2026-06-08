import math
from dataclasses import dataclass

from rescue_pc_brain import control_config as cfg


@dataclass
class DriveCommand:
    linear_x: float
    angular_z: float
    target_speed: float
    raw_steer: float
    applied_steer: float
    max_steer_allowed: float


class DriveCommandBuilder:
    def clamp(self, value, min_value=-1.0, max_value=1.0):
        if value > max_value:
            return max_value

        if value < min_value:
            return min_value

        return value

    def get_max_steer_allowed(self, real_speed_abs):
        """
        Calcula cuánto giro se permite según la velocidad real.

        Regla:
        - Si el robot está casi quieto, permite giro completo.
        - Si el robot va rápido, limita el giro.
        """

        real_speed_abs = abs(real_speed_abs)
        real_speed_abs = self.clamp(real_speed_abs, 0.0, 1.0)

        # Robot quieto o casi quieto:
        # se permite giro sobre su propio eje.
        if real_speed_abs <= cfg.PIVOT_ALLOWED_REAL_SPEED:
            return 1.0

        # Normalizamos desde el umbral de pivote hasta velocidad máxima.
        speed_range = 1.0 - cfg.PIVOT_ALLOWED_REAL_SPEED

        if speed_range <= 0.0:
            return cfg.MIN_STEER_AT_MAX_SPEED

        speed_ratio = (
            real_speed_abs - cfg.PIVOT_ALLOWED_REAL_SPEED
        ) / speed_range

        speed_ratio = self.clamp(speed_ratio, 0.0, 1.0)

        # A medida que sube la velocidad real,
        # baja el giro máximo permitido.
        max_steer = 1.0 - (
            1.0 - cfg.MIN_STEER_AT_MAX_SPEED
        ) * speed_ratio

        return self.clamp(
            max_steer,
            cfg.MIN_STEER_AT_MAX_SPEED,
            1.0
        )

    def limit_steer_by_real_speed(self, raw_steer, real_speed_abs):
        """
        Limita el joystick X según velocidad real.

        Si vas lento:
            raw_steer puede llegar a 1.0

        Si vas rápido:
            raw_steer se recorta, por ejemplo, a 0.35
        """

        max_steer_allowed = self.get_max_steer_allowed(real_speed_abs)

        applied_steer = self.clamp(
            raw_steer,
            -max_steer_allowed,
            max_steer_allowed
        )

        return applied_steer, max_steer_allowed

    def build(self, controller_state, gearbox_manager, real_speed_abs=0.0):
        """
        Construye linear.x y angular.z.

        Caja:
            define el máximo de velocidad disponible.

        R2:
            multiplica la velocidad.

        Joystick:
            define intención de movimiento y giro.

        Seguridad de giro:
            si real_speed_abs es alta, se limita el giro máximo.
            si real_speed_abs es baja, se permite giro sobre el propio eje.
        """

        joystick_x = self.clamp(controller_state.joystick_x, -1.0, 1.0)
        joystick_y = self.clamp(controller_state.joystick_y, -1.0, 1.0)

        joystick_magnitude = math.sqrt(
            joystick_x ** 2 +
            joystick_y ** 2
        )

        joystick_magnitude = self.clamp(joystick_magnitude, 0.0, 1.0)

        raw_steer = joystick_x

        applied_steer, max_steer_allowed = self.limit_steer_by_real_speed(
            raw_steer,
            real_speed_abs
        )

        r2 = controller_state.r2_value
        gear_limit = gearbox_manager.get_gear_limit()
        direction = gearbox_manager.direction_sign()

        target_speed = joystick_magnitude * r2 * gear_limit

        linear_x = (
            target_speed *
            direction *
            (1.0 - abs(applied_steer)) *
            cfg.MAX_LINEAR_SPEED
        )

        angular_z = (
            target_speed *
            applied_steer *
            cfg.MAX_ANGULAR_SPEED
        )

        linear_x = self.clamp(linear_x)
        angular_z = self.clamp(angular_z)

        return DriveCommand(
            linear_x=linear_x,
            angular_z=angular_z,
            target_speed=target_speed,
            raw_steer=raw_steer,
            applied_steer=applied_steer,
            max_steer_allowed=max_steer_allowed
        )