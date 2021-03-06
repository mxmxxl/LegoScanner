import numpy as np
from .lego_connector import LegoConnector
from .devices import Device
from .config import SYSTEM_CONFIG, DEVICES_CONFIG, OBJECTS_CONFIG, SENSORS_CONFIG, ACTIONABLES_CONFIG

class System:
    def __init__(self, brick_ip='ev3dev.local', get_state_mode=None):

        if get_state_mode is None: # fallback to default if not specified
            self.get_state_mode = SYSTEM_CONFIG.get_state_mode
        else:
            self.get_state_mode = get_state_mode

        self.LC = LegoConnector(brick_ip)

        self.init_pos = {'bot': 0, 'top': 0 }

        devices = {}
        for key in DEVICES_CONFIG.keys():
            # fetch devices from the LEGO interface
            devices[key] = {name: self.LC.get_device(conf[0], conf[1]) for (name, conf) in DEVICES_CONFIG[key].items()}
            # wrap them in Env abstraction to expose get_state and perform_action

            for (name, device) in devices[key].items():
                devices[key][name] = eval(OBJECTS_CONFIG[key])(device)

            #for name in devices[key].keys():
            #    devices[key][name] = eval(OBJECTS_CONFIG[key])(devices[key][name])

        print(devices)
            
        self.devices = devices


    def get_state(self):
        # the get_state() method is defined in each of the EnvSensor objects
        return {
            'list': [device.get_state() for device in self.devices['sensors'].values()],
            'dict': {name: device.get_state() for (name, device) in self.devices['sensors'].items()}
        }[self.get_state_mode]

    def perform_actions(self, actions):
        if type(actions) == list:
            for actionable, action in zip(self.devices['actionables'].values(), actions):
                actionable.perform_action(action)
        elif type(actions) == dict:
            for key, action in actions.items():
                self.devices['actionables'][key].perform_action(action)
        else:
            raise ValueError('Actions have to be of type list or dict. Provided:', type(actions))

    def get_action_space(self, mode='list'):
        # mode: 'list' or 'dict'
        return {
            'list': [actionable.possible_actions for actionable in self.devices['actionables'].values()],
            'dict': {name: actionable.possible_actions for (name, actionable) in self.devices['actionables'].items()}
        }[mode]

    def stop(self):
        for actionable in self.devices['actionables'].values():
            actionable.perform_stop_action()

    def reset(self):
        for actionable in self.devices['actionables'].values():
            actionable.perform_reset_action()

    def go_to_init_state(self):
        # This is a hack and shouldn't be like this. Since the motor shoudl be available even when they are note sensors
        self.devices['actionables']['bot'].actionable_object.motor.run_to_abs_pos(position_sp = self.init_pos['bot'], speed_sp = 100)
        self.devices['actionables']['top'].actionable_object.motor.run_to_abs_pos(position_sp = self.init_pos['top'], speed_sp = 100)

        while self.devices['actionables']['top'].actionable_object.motor.is_running or self.devices['actionables']['bot'].actionable_object.motor.is_running:
            pass

        self.devices['actionables']['bot'].actionable_object.motor.run_direct(duty_cycle_sp = 0)
        self.devices['actionables']['top'].actionable_object.motor.run_direct(duty_cycle_sp = 0)

    def disconnect(self, stop=True):
        if stop:
            self.stop()
        del(self.LC)

class EnvSensor:
    def __init__(self, device_object):
        assert isinstance(device_object, Device)

        self.sensor = device_object.object
        self.relevant_fields = SENSORS_CONFIG[device_object.type]

    def get_state(self):
        return tuple(getattr(self.sensor, field) for field in self.relevant_fields)

class EnvActionable:
    def __init__(self, device_object):
        assert type(device_object) is Device

        self.actionable_object = ACTIONABLES_CONFIG[device_object.type][0](device_object)
        self.possible_actions = ACTIONABLES_CONFIG[device_object.type][1]

        self.perform_stop_action = self.actionable_object.stop_action_function
        self.perform_reset_action = self.actionable_object.reset_action_function

    def perform_action(self, action):
        if self.possible_actions:
            self.actionable_object.action_function(self.possible_actions[action])
        else:
            self.actionable_object.action_function(action)