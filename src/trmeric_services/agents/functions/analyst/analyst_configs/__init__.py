"""Analyst configuration module."""
from .project.project import project_config_dict as project_config
from .roadmap.roadmap import roadmap_config_dict as roadmap_config
from .capacity.capacity import capacity_config_dict as capacity_config

ANALYZER_CONFIGS = {
    "project": project_config,
    "roadmap": roadmap_config,
    "capacity": capacity_config,
}


