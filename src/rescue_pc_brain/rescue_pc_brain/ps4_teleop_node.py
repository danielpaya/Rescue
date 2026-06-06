import json

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, String

from rescue_pc_brain.controller_mapper import ControllerMapper
from rescue_pc_brain.gearbox_manager import GearboxManager
from rescue_pc_brain.drive_command_builder import DriveCommandBuilder


class PS4TeleopNode(Node):
    def __init__(self):
        super().__init__('ps4_teleop_node')

        # =========================
        # Módulos de lógica
        # =========================

        self.controller_mapper = ControllerMapper()
        self.gearbox_manager = GearboxManager()
        self.drive_command_builder = DriveCommandBuilder()

        # Velocidad real reportada por la Raspberry.
        self.real_speed_abs = 0.0

        # Share funciona como interruptor de habilitación.
        self.movement_enabled = False
        self.last_share_state = 0

        # Últimos valores para dashboard.
        self.last_controller_state = None
        self.last_target_speed = 0.0
        self.last_linear_x = 0.0
        self.last_angular_z = 0.0
        self.last_status_text = 'BLOQUEADO POR SHARE'
        self.last_brake_intensity = 0.0

        # Contador para no saturar terminal.
        self.log_counter = 0

        # =========================
        # ROS 2
        # =========================

        self.joy_subscription = self.create_subscription(
            Joy,
            '/joy',
            self.joy_callback,
            10
        )

        self.real_speed_subscription = self.create_subscription(
            Float32,
            '/real_speed_abs',
            self.real_speed_callback,
            10
        )

        self.cmd_vel_publisher = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )

        self.drive_status_publisher = self.create_publisher(
            String,
            '/drive_status',
            10
        )

        self.brake_intensity_publisher = self.create_publisher(
            Float32,
            '/brake_intensity',
            10
        )

        self.status_timer = self.create_timer(
            0.2,
            self.publish_periodic_status
        )

        self.get_logger().info('Nodo PS4 Teleop iniciado.')
        self.get_logger().info('Nueva lógica: cajas + R2 + reversa segura.')
        self.get_logger().info('Share habilita/deshabilita movimiento.')
        self.get_logger().info('Publicando /drive_status para interfaz gráfica.')
        self.get_logger().info('Publicando /brake_intensity para freno progresivo.')

    # =========================
    # Callback de velocidad real
    # =========================

    def real_speed_callback(self, msg):
        self.real_speed_abs = msg.data

    # =========================
    # Publicaciones auxiliares
    # =========================

    def publish_stop(self):
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        self.cmd_vel_publisher.publish(cmd)

    def publish_brake_intensity(self, value):
        self.last_brake_intensity = float(value)

        msg = Float32()
        msg.data = float(value)

        self.brake_intensity_publisher.publish(msg)

    # =========================
    # Toggle con botón Share
    # =========================

    def update_movement_toggle(self, controller_state):
        share_pressed = controller_state.share_pressed

        # Detectar flanco de subida: 0 -> 1
        if share_pressed == 1 and self.last_share_state == 0:
            self.movement_enabled = not self.movement_enabled

            if self.movement_enabled:
                self.last_status_text = 'MOVIMIENTO HABILITADO'
                self.get_logger().info('Movimiento HABILITADO con Share.')
            else:
                self.last_status_text = 'BLOQUEADO POR SHARE'
                self.last_target_speed = 0.0
                self.last_linear_x = 0.0
                self.last_angular_z = 0.0
                self.publish_stop()
                self.publish_brake_intensity(0.0)
                self.get_logger().info('Movimiento DESHABILITADO con Share.')

        self.last_share_state = share_pressed

    # =========================
    # Estado para dashboard
    # =========================

    def publish_drive_status(
        self,
        controller_state=None,
        target_speed=0.0,
        linear_x=0.0,
        angular_z=0.0,
        movement_enabled=False,
        status_text='OK'
    ):
        payload = {
            'gear': self.gearbox_manager.current_gear,
            'direction': self.gearbox_manager.direction,
            'target_speed': float(target_speed),
            'real_speed_abs': float(self.real_speed_abs),
            'brake_intensity': float(self.last_brake_intensity),
            'linear_x': float(linear_x),
            'angular_z': float(angular_z),
            'movement_enabled': bool(movement_enabled),
            'status_text': status_text,
        }

        if controller_state is not None:
            payload.update({
                'r2': float(controller_state.r2_value),
                'joy_x': float(controller_state.joystick_x),
                'joy_y': float(controller_state.joystick_y),
                'l1_pressed': int(controller_state.l1_pressed),
                'l2_pressed': int(controller_state.l2_pressed),
                'share_pressed': int(controller_state.share_pressed),
                'x_pressed': int(controller_state.x_pressed),
                'circle_pressed': int(controller_state.circle_pressed),
                'triangle_pressed': int(controller_state.triangle_pressed),
            })

            if hasattr(controller_state, 'l2_value'):
                payload['l2_value'] = float(controller_state.l2_value)
            else:
                payload['l2_value'] = 0.0

        else:
            payload.update({
                'r2': 0.0,
                'joy_x': 0.0,
                'joy_y': 0.0,
                'l1_pressed': 0,
                'l2_pressed': 0,
                'share_pressed': 0,
                'x_pressed': 0,
                'circle_pressed': 0,
                'triangle_pressed': 0,
                'l2_value': 0.0,
            })

        msg = String()
        msg.data = json.dumps(payload)

        self.drive_status_publisher.publish(msg)

    def publish_periodic_status(self):
        self.publish_drive_status(
            controller_state=self.last_controller_state,
            target_speed=self.last_target_speed,
            linear_x=self.last_linear_x,
            angular_z=self.last_angular_z,
            movement_enabled=self.movement_enabled,
            status_text=self.last_status_text
        )

    # =========================
    # Callback principal del control
    # =========================

    def joy_callback(self, msg):
        controller_state = self.controller_mapper.from_joy_msg(msg)

        self.last_controller_state = controller_state

        # Share habilita/deshabilita movimiento.
        self.update_movement_toggle(controller_state)

        # Primero actualizamos cajas y dirección.
        # Esto permite cambiar caja aunque el movimiento esté bloqueado.
        self.gearbox_manager.update(
            controller_state,
            self.real_speed_abs
        )

        l1_pressed = controller_state.l1_pressed == 1
        circle_pressed = controller_state.circle_pressed == 1

        # =========================
        # Freno
        # =========================
        # Círculo solo = freno normal.
        # L2 + Círculo = freno fuerte/progresivo.
        # L1 + Círculo = bajar caja, no frenar.
        if circle_pressed and not l1_pressed:
            if hasattr(controller_state, 'l2_value'):
                brake_intensity = controller_state.l2_value
            else:
                brake_intensity = 0.0

            self.publish_stop()
            self.publish_brake_intensity(brake_intensity)

            self.last_target_speed = 0.0
            self.last_linear_x = 0.0
            self.last_angular_z = 0.0

            if brake_intensity > 0.10:
                self.last_status_text = f'FRENANDO FUERTE L2={brake_intensity:.2f}'
            else:
                self.last_status_text = 'FRENANDO NORMAL'

            self.publish_drive_status(
                controller_state=controller_state,
                target_speed=self.last_target_speed,
                linear_x=self.last_linear_x,
                angular_z=self.last_angular_z,
                movement_enabled=self.movement_enabled,
                status_text=self.last_status_text
            )

            self.get_logger().info(self.last_status_text)
            return

        # =========================
        # Bloqueo por Share
        # =========================

        if not self.movement_enabled:
            self.publish_stop()
            self.publish_brake_intensity(0.0)

            self.last_target_speed = 0.0
            self.last_linear_x = 0.0
            self.last_angular_z = 0.0
            self.last_status_text = 'BLOQUEADO POR SHARE'

            self.publish_drive_status(
                controller_state=controller_state,
                target_speed=self.last_target_speed,
                linear_x=self.last_linear_x,
                angular_z=self.last_angular_z,
                movement_enabled=False,
                status_text=self.last_status_text
            )

            self.log_counter += 1

            if self.log_counter >= 25:
                self.log_counter = 0

                self.get_logger().info(
                    f'Movimiento bloqueado por Share. '
                    f'gear={self.gearbox_manager.current_gear}, '
                    f'direction={self.gearbox_manager.direction}, '
                    f'real_speed_abs={self.real_speed_abs:.3f}'
                )

            return

        # =========================
        # Movimiento normal
        # =========================

        drive_command = self.drive_command_builder.build(
            controller_state,
            self.gearbox_manager
        )

        cmd = Twist()
        cmd.linear.x = drive_command.linear_x
        cmd.angular.z = drive_command.angular_z

        self.cmd_vel_publisher.publish(cmd)
        self.publish_brake_intensity(0.0)

        self.last_target_speed = drive_command.target_speed
        self.last_linear_x = cmd.linear.x
        self.last_angular_z = cmd.angular.z
        self.last_status_text = 'MOVIMIENTO HABILITADO'

        self.publish_drive_status(
            controller_state=controller_state,
            target_speed=self.last_target_speed,
            linear_x=self.last_linear_x,
            angular_z=self.last_angular_z,
            movement_enabled=True,
            status_text=self.last_status_text
        )

        self.log_counter += 1

        if self.log_counter >= 10:
            self.log_counter = 0

            self.get_logger().info(
                f'gear={self.gearbox_manager.current_gear}, '
                f'direction={self.gearbox_manager.direction}, '
                f'real_speed_abs={self.real_speed_abs:.3f}, '
                f'r2={controller_state.r2_value:.3f}, '
                f'joy_x={controller_state.joystick_x:.3f}, '
                f'joy_y={controller_state.joystick_y:.3f}, '
                f'brake={self.last_brake_intensity:.3f}, '
                f'target_speed={drive_command.target_speed:.3f}, '
                f'linear.x={cmd.linear.x:.3f}, '
                f'angular.z={cmd.angular.z:.3f}'
            )


def main(args=None):
    rclpy.init(args=args)

    node = PS4TeleopNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()