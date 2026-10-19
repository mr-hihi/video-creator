class FilmNotFoundError(Exception):
    pass


class FilmProjectNotFoundError(FilmNotFoundError):
    def __init__(self, project_id: str):
        super().__init__(f"Film project {project_id} not found")


class CharacterNotFoundError(FilmNotFoundError):
    def __init__(self, character_id: str):
        super().__init__(f"Character {character_id} not found")


class StyleNotFoundError(FilmNotFoundError):
    def __init__(self, style_id: str):
        super().__init__(f"Style {style_id} not found")


class VoiceNotFoundError(FilmNotFoundError):
    def __init__(self, voice_id: str):
        super().__init__(f"Voice {voice_id} not found")


class EpisodeNotFoundError(FilmNotFoundError):
    def __init__(self, episode_id: str):
        super().__init__(f"Episode {episode_id} not found")


class PartNotFoundError(FilmNotFoundError):
    def __init__(self, part_id: str):
        super().__init__(f"Part {part_id} not found")


class SceneNotFoundError(FilmNotFoundError):
    def __init__(self, scene_id: str):
        super().__init__(f"Scene {scene_id} not found")


class FilmRequestNotFoundError(FilmNotFoundError):
    def __init__(self, request_id: str):
        super().__init__(f"Generation request {request_id} not found")


class FilmFileNotFoundError(FilmNotFoundError):
    def __init__(self, relative_path: str):
        super().__init__(f"File {relative_path} not found")


class InvalidFilmRequestError(Exception):
    pass


class FilmConflictError(Exception):
    pass


class ProjectArchivedError(FilmConflictError):
    def __init__(self, project_id: str):
        super().__init__(f"Film project {project_id} is archived")


class EpisodeRunningError(FilmConflictError):
    def __init__(self, episode_number: int):
        super().__init__(f"Episode {episode_number} is running — stop it first")


class EpisodeActionNotAllowedError(FilmConflictError):
    def __init__(self, action: str, episode_number: int, status: str):
        super().__init__(f"Cannot {action} episode {episode_number} while it is {status}")


class FilmFileTooLargeError(Exception):
    pass


class EpisodeStepFailedError(Exception):
    pass
