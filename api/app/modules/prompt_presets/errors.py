class PromptPresetNotFoundError(Exception):
    def __init__(self, preset_id: str):
        super().__init__(f"Prompt preset {preset_id} not found")
        self.preset_id = preset_id


class PresetVersionNotFoundError(Exception):
    def __init__(self, preset_id: str, version: int):
        super().__init__(f"Version {version} of preset {preset_id} not found")


class InvalidPresetError(Exception):
    pass


class PresetConflictError(Exception):
    pass


class PresetFileTooLargeError(Exception):
    pass
