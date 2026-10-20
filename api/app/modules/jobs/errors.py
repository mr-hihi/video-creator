class JobNotFoundError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} not found")
        self.job_id = job_id


class InvalidUploadError(Exception):
    pass


class InvalidYoutubeJobError(Exception):
    pass


class YoutubeUnreachableError(Exception):
    pass


class ResultNotReadyError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} has no result yet")
        self.job_id = job_id


class ResultFileNotFoundError(Exception):
    def __init__(self, relative_path: str):
        super().__init__(f"Result file {relative_path} not found")
        self.relative_path = relative_path


class JobPresetNotFoundError(Exception):
    def __init__(self, preset_id: str):
        super().__init__(f"Prompt preset {preset_id} not found")


class InvalidFilmAnalysisJobError(Exception):
    pass


class JobNotDeletableError(Exception):
    def __init__(self):
        super().__init__("Only film analysis jobs can be deleted")


class JobStillRunningError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} is still running")


class NotFilmAnalysisJobError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} is not a film analysis")


class NoVideoNotesError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} has no video notes to reuse")


class NoCompressedVideoError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} has no compressed video to reuse")


class NoZipDownloadError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} has no zip download")
