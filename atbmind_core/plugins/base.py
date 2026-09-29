"""
ATBMind Plugin Service Provider Interface (SPI)
Defines the standard abstract base class that domain plugins must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from atbmind_core.plugins.schemas import (
    PluginUISpec,
    TemplateMetadata,
    WorkflowStep,
    WorkflowResult,
)

class ATBMindPlugin(ABC):
    """
    Standard plugin interface for ATBMind.
    Decouples core middleware capabilities from domain-specific plugins (Draw, 3D, CAD, etc.).
    """

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """
        Unique identifier for the plugin (e.g. 'draw', 'model_3d', 'cad').
        Must be lowercase alphanumeric and hyphens/underscores only.
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Semver version string of the plugin (e.g. '1.0.0').
        """
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Lifecycle initialization hook called by PluginRegistry upon registration.

        Args:
            config: Plugin-specific configuration section from AppConfig.
        """
        pass

    @abstractmethod
    def get_templates(self) -> List[TemplateMetadata]:
        """
        Returns the collection of prompt and instruction templates provided by this plugin.
        These templates are indexed into local storage for matching and workflow planning.
        """
        pass

    @abstractmethod
    def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
        """
        Extracts domain-specific contextual entities (e.g., CV detection of human subjects and masks)
        from raw inputs before intent completion.

        Args:
            raw_input: Raw user input such as image path, binary data, or text context.

        Returns:
            Dict containing detected entities and metadata.
        """
        pass

    @abstractmethod
    def get_domain_prompt_injection(self) -> str:
        """
        Provides domain commonsense guidelines and latent intent completion rules
        injected into Layer 1 (Latent Intent Completer).
        """
        pass

    @abstractmethod
    def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
        """
        Executes a planned workflow step using the plugin's underlying model adapters.

        Args:
            step: The WorkflowStep definition containing template_id and bound slots.
            context: Execution context containing original inputs, previous step outputs, etc.

        Returns:
            WorkflowResult: Result payload with status and artifacts.
        """
        pass

    def get_ui_spec(self) -> Optional[PluginUISpec]:
        """
        Returns the UI specification for host UI controls (FooterDock, StylePopover),
        or None if the plugin operates headless without dedicated UI controls.
        """
        return None

