from collections.abc import Collection, Sequence

from app.modules.films.models import Character, FilmProject
from app.modules.films.repository import FilmRepository
from app.modules.films.views import CharacterSummary, ProjectSummary


class FilmSummaries:
    def __init__(self, repository: FilmRepository):
        self._repository = repository

    def summarize_projects(self, projects: Sequence[FilmProject]) -> list[ProjectSummary]:
        style_names_by_id = self._find_style_names({project.style_id for project in projects})
        episode_counts_by_project_id = self._repository.count_episodes_by_project(
            [project.id for project in projects]
        )
        return [
            ProjectSummary(
                project=project,
                style_name=style_names_by_id[project.style_id],
                episode_count=episode_counts_by_project_id.get(project.id, 0),
            )
            for project in projects
        ]

    def summarize_characters(self, characters: Sequence[Character]) -> list[CharacterSummary]:
        style_names_by_id = self._find_style_names({character.style_id for character in characters})
        project_counts_by_character_id = self._repository.count_projects_by_character(
            [character.id for character in characters]
        )
        return [
            CharacterSummary(
                character=character,
                style_name=style_names_by_id[character.style_id],
                project_count=project_counts_by_character_id.get(character.id, 0),
            )
            for character in characters
        ]

    def _find_style_names(self, style_ids: Collection[str]) -> dict[str, str]:
        styles_by_id = self._repository.find_styles_by_ids(style_ids)
        return {style_id: style.name for style_id, style in styles_by_id.items()}
