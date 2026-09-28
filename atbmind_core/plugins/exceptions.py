"""
ATBMind Plugin Exception Hierarchy
Defines standard errors raised across plugin lifecycle and execution phases.
"""

class ATBMindPluginError(Exception):
    """Base exception for all plugin-related failures."""
    pass

class PluginNotFoundError(ATBMindPluginError):
    """Raised when a requested plugin ID cannot be found or is not loaded."""
    pass

class PluginLoadError(ATBMindPluginError):
    """Raised when a plugin fails during discovery, import, or initialization."""
    pass

class PluginExecutionError(ATBMindPluginError):
    """Raised when an error occurs during execution of a workflow step."""
    pass

class PluginValidationError(ATBMindPluginError):
    """Raised when plugin inputs, metadata, or outputs fail schema validation."""
    pass

class CyclicDependencyError(ATBMindPluginError):
    """Raised when template dependencies form a cycle in the workflow DAG."""
    pass

