import subprocess

def get_git_version():
    '''Gets the Git version (for status endpoint).'''
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--always', '--dirty'],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"
    
distribution_version = get_git_version()