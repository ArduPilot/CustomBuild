# common/config.py

# Build timeout in seconds.
# Used independently by:
#  - build_manager.progress_updater (state transition)
#  - builder.builder (process termination)
BUILD_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
