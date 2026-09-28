"""
ATBMind Plugin Registry and Discovery Service
Coordinates plugin lifecycle, dynamic directory scanning, and entry_points discovery.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.exceptions import (
    PluginNotFoundError,
    PluginValidationError,
    PluginLoadError,
)

logger = logging.getLogger("atbmind.plugins.registry")

class PluginRegistry:
    """
    Central registry for managing ATBMind plugin lifecycle,
    providing dynamic loading from disk and entry_points.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, ATBMindPlugin] = {}
        self.failed_plugins: Dict[str, str] = {}

    def register_plugin(self, plugin: ATBMindPlugin, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Registers and initializes an ATBMindPlugin instance.

        Args:
            plugin: Concrete ATBMindPlugin instance.
            config: Optional configuration dictionary passed to initialize().
        """
        if not isinstance(plugin, ATBMindPlugin):
            raise PluginValidationError(f"Object {plugin} is not an instance of ATBMindPlugin.")

        plugin_id = plugin.plugin_id
        if not plugin_id or not isinstance(plugin_id, str):
            raise PluginValidationError(f"Invalid plugin_id '{plugin_id}' for plugin {plugin}.")

        if plugin_id in self._plugins:
            raise PluginValidationError(f"Plugin with ID '{plugin_id}' is already registered.")

        try:
            plugin.initialize(config or {})
        except Exception as e:
            raise PluginLoadError(f"Failed to initialize plugin '{plugin_id}': {e}") from e

        self._plugins[plugin_id] = plugin
        logger.info("Successfully registered plugin: %s (v%s)", plugin_id, plugin.version)

    def unregister_plugin(self, plugin_id: str) -> None:
        """Unregisters an active plugin."""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            logger.info("Unregistered plugin: %s", plugin_id)

    def get_plugin(self, plugin_id: str) -> ATBMindPlugin:
        """
        Retrieves a registered plugin by ID.

        Raises:
            PluginNotFoundError: If plugin_id is not registered.
        """
        if plugin_id not in self._plugins:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found in registry.")
        return self._plugins[plugin_id]

    def list_plugins(self) -> List[str]:
        """Returns sorted list of registered plugin IDs."""
        return sorted(list(self._plugins.keys()))

    def get_all_plugins(self) -> Dict[str, ATBMindPlugin]:
        """Returns a dictionary copy of all active plugins."""
        return dict(self._plugins)

    def clear(self) -> None:
        """Clears all active plugins and recorded failures."""
        self._plugins.clear()
        self.failed_plugins.clear()

    def scan_directory(
        self, dir_path: str | Path, config: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Scans a directory for plugin implementations and registers them.
        Looks for `<subdir>/plugin.py` or `<plugin_file>.py`.

        Args:
            dir_path: Directory path to scan.
            config: Global or plugin-specific configuration mapping.

        Returns:
            int: Number of newly registered plugins.
        """
        path = Path(dir_path)
        if not path.is_dir():
            logger.warning("Plugins directory %s does not exist.", path)
            return 0

        registered_count = 0

        # Collect candidate python files
        candidate_files: List[Path] = []
        for item in sorted(path.iterdir()):
            if item.is_dir() and (item / "plugin.py").is_file():
                candidate_files.append(item / "plugin.py")
            elif item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                candidate_files.append(item)

        for py_file in candidate_files:
            try:
                mod_name = f"atbmind_plugin_{py_file.stem}_{abs(hash(str(py_file)))}"
                spec = importlib.util.spec_from_file_location(mod_name, py_file)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot create spec for {py_file}")

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find ATBMindPlugin subclasses defined in the module
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, ATBMindPlugin) and obj is not ATBMindPlugin:
                        # Instantiate and register
                        plugin_cfg = (config or {}).get(getattr(obj, "plugin_id", "")) or {}
                        instance = obj()
                        self.register_plugin(instance, plugin_cfg)
                        registered_count += 1
            except Exception as e:
                err_msg = f"Failed to load plugin from {py_file}: {e}"
                logger.error(err_msg)
                self.failed_plugins[str(py_file)] = err_msg

        return registered_count

    def scan_entry_points(
        self, group: str = "atbmind.plugins", config: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Scans installed Python packages via entry_points for plugins.

        Args:
            group: entry_points group name (defaults to 'atbmind.plugins').
            config: Configuration dictionary.

        Returns:
            int: Number of newly registered plugins.
        """
        registered_count = 0
        try:
            eps = importlib.metadata.entry_points(group=group)
        except Exception as e:
            logger.error("Failed to query entry_points for group %s: %e", group, e)
            return 0

        for ep in eps:
            try:
                cls_or_factory = ep.load()
                instance = cls_or_factory() if inspect.isclass(cls_or_factory) else cls_or_factory
                plugin_cfg = (config or {}).get(instance.plugin_id) or {}
                self.register_plugin(instance, plugin_cfg)
                registered_count += 1
            except Exception as e:
                err_msg = f"Failed to load entry_point '{ep.name}': {e}"
                logger.error(err_msg)
                self.failed_plugins[ep.name] = err_msg

        return registered_count

    def scan_all(
        self, plugins_dir: Optional[str | Path] = None, config: Optional[Dict[str, Any]] = None
    ) -> int:
        """Scans both directory and entry_points."""
        total = 0
        if plugins_dir:
            total += self.scan_directory(plugins_dir, config)
        total += self.scan_entry_points(config=config)
        return total

_GLOBAL_REGISTRY: Optional[PluginRegistry] = None

def get_plugin_registry(reset: bool = False) -> PluginRegistry:
    """
    Returns the singleton instance of PluginRegistry.

    Args:
        reset: If True, resets and creates a clean registry instance.
    """
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None or reset:
        _GLOBAL_REGISTRY = PluginRegistry()
    return _GLOBAL_REGISTRY
