class FilmCloneNotFoundError(Exception):
    def __init__(self, clone_id: str):
        super().__init__(f"Film clone {clone_id} not found")


class CloneAssetNotFoundError(Exception):
    def __init__(self, asset_id: str):
        super().__init__(f"Asset {asset_id} not found")


class CloneSceneNotFoundError(Exception):
    def __init__(self, scene_id: str):
        super().__init__(f"Scene {scene_id} not found")


class CloneFileNotFoundError(Exception):
    def __init__(self, relative_path: str):
        super().__init__(f"File {relative_path} not found")


class InvalidCloneRequestError(Exception):
    pass


class CloneConflictError(Exception):
    pass


class CloneActionNotAllowedError(CloneConflictError):
    def __init__(self, action: str, clone_id: str, status: str, step: str):
        super().__init__(f"Cannot {action} clone {clone_id} while it is {status} at {step}")


class CloneStepFailedError(Exception):
    pass
