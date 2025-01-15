import os
import sys
from ap_git import GitRepo
from build_manager import BuildManager
from builder import Builder
from metadata_manager import (
    APSourceMetadataFetcher,
)
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        },
    },
    'handlers': {
        'stream': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': sys.stdout,
        },
    },
    'loggers': {
        'root': {
            'level': 'INFO',
            'handlers': ['stream'],
        },
    },
})

if __name__ == "__main__":
    basedir = os.path.abspath(os.getenv("CBS_BASEDIR"))
    workdir = os.path.abspath('/workdir')

    repo = GitRepo.clone_if_needed(
        source="https://github.com/ardupilot/ardupilot.git",
        dest=os.path.join(workdir, 'ardupilot'),
    )

    ap_metafetch = APSourceMetadataFetcher(
        ap_repo=repo
    )

    manager = BuildManager(
        outdir=os.path.join(basedir, 'builds'),
        redis_host=os.getenv('CBS_REDIS_HOST', default='localhost'),
        redis_port=os.getenv('CBS_REDIS_PORT', default='6379')
    )

    builder = Builder(
        workdir=workdir,
        source_repo=repo,
    )
    builder.run()
