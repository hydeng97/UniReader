from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict
import yaml
from backend.models import APIConfig, PromptConfig, MinerUConfig
from core.path_utils import get_data_dir, get_config_file

DEFAULT_PROMPTS = [
    {
        "id": "general",
        "name": "通用解读",
        "prompt": "请对这篇论文进行全面的分析和解读，包括：1. 研究背景和动机 2. 核心方法和创新点 3. 主要实验结果 4. 结论和局限性",
        "is_enabled": True,
    },
    {
        "id": "simple",
        "name": "通俗解读",
        "prompt": "请用通俗易懂的语言解释这篇论文的主要内容和贡献，让非专业人士也能理解。",
        "is_enabled": True,
    },
    {
        "id": "technical",
        "name": "技术细节",
        "prompt": "请深入分析这篇论文的技术细节，包括：1. 具体的算法和模型架构 2. 数学推导和公式解释 3. 实验设置和超参数 4. 代码实现要点",
        "is_enabled": True,
    },
]

DEFAULT_CLIENT_CONFIG = {
    "max_concurrent_requests": 5,
    "request_timeout": 120,
    "total_request_timeout": 300,
    "cleanup_interval": 60,
    "batch_import_delay": 2,
}


class ConfigManager:
    def __init__(self):
        self.config_dir = get_data_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = get_config_file()
        self.api_configs_file = self.config_dir / "api_configs.json"
        self.prompt_configs_file = self.config_dir / "prompt_configs.json"
        self.mineru_configs_file = self.config_dir / "mineru_configs.json"
        self.current_api_file = self.config_dir / "current_api.json"
        self.current_mineru_file = self.config_dir / "current_mineru.json"
        self.client_config_file = self.config_dir / "client_config.json"

        self._api_configs: Dict[str, APIConfig] = {}
        self._prompt_configs: Dict[str, PromptConfig] = {}
        self._mineru_configs: Dict[str, MinerUConfig] = {}
        self._current_api_id: Optional[str] = None
        self._current_mineru_id: Optional[str] = None
        self._server_config: Dict = {}
        self._client_config: Dict = {}

        self._load_configs()

    def _load_configs(self):
        self._load_from_yaml()

        if self.api_configs_file.exists():
            with open(self.api_configs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_names = {c.name for c in self._api_configs.values()}
                for k, v in data.items():
                    if k not in self._api_configs:
                        config = APIConfig(**v)
                        if config.name not in existing_names:
                            self._api_configs[k] = config

        if self.prompt_configs_file.exists():
            with open(self.prompt_configs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_names = {c.name for c in self._prompt_configs.values()}
                for k, v in data.items():
                    if k not in self._prompt_configs:
                        config = PromptConfig(**v)
                        if config.name not in existing_names:
                            self._prompt_configs[k] = config

        if not self._prompt_configs:
            for p in DEFAULT_PROMPTS:
                self._prompt_configs[p["id"]] = PromptConfig(**p)
            self._save_prompts()

        if self.mineru_configs_file.exists():
            with open(self.mineru_configs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_names = {c.name for c in self._mineru_configs.values()}
                for k, v in data.items():
                    if k not in self._mineru_configs:
                        config = MinerUConfig(**v)
                        if config.name not in existing_names:
                            self._mineru_configs[k] = config

        if self.current_api_file.exists():
            with open(self.current_api_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_id = data.get("current_api_id")
                if saved_id and saved_id in self._api_configs:
                    self._current_api_id = saved_id

        if self.current_mineru_file.exists():
            with open(self.current_mineru_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_id = data.get("current_mineru_id")
                if saved_id and saved_id in self._mineru_configs:
                    self._current_mineru_id = saved_id

        self._save_all()

    def _load_from_yaml(self):
        if not self.config_file.exists():
            return

        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            return

        llm_apis = config.get("llm_apis", [])
        for api in llm_apis:
            if not api.get("api_key") or api["api_key"] == "your-api-key-here":
                continue
            config_id = str(uuid.uuid4())[:8]
            self._api_configs[config_id] = APIConfig(
                id=config_id,
                name=api.get("name", "Unnamed"),
                base_url=api.get("base_url", ""),
                api_key=api.get("api_key", ""),
                model=api.get("model", ""),
                is_default=api.get("is_default", False),
            )
            if api.get("is_default") or not self._current_api_id:
                self._current_api_id = config_id

        mineru_configs = config.get("mineru", [])
        for mc in mineru_configs:
            if not mc.get("token") or mc["token"] == "your-mineru-token-here":
                continue
            config_id = str(uuid.uuid4())[:8]
            self._mineru_configs[config_id] = MinerUConfig(
                id=config_id,
                name=mc.get("name", "MinerU"),
                token=mc.get("token", ""),
                is_default=mc.get("is_default", False),
            )
            if mc.get("is_default") or not self._current_mineru_id:
                self._current_mineru_id = config_id

        prompts = config.get("prompts", [])
        for p in prompts:
            config_id = str(uuid.uuid4())[:8]
            self._prompt_configs[config_id] = PromptConfig(
                id=config_id,
                name=p.get("name", "Unnamed"),
                prompt=p.get("prompt", ""),
                is_enabled=p.get("is_enabled", True),
            )

        self._server_config = config.get("server", {})
        self._client_config = {**DEFAULT_CLIENT_CONFIG, **config.get("client", {})}

    def _save_all(self):
        self._save_apis()
        self._save_prompts()
        self._save_mineru()
        self._save_current_api()
        self._save_current_mineru()

    def get_server_config(self) -> Dict:
        return self._server_config

    def get_client_config(self) -> Dict:
        return self._client_config

    def save_client_config(self, config: Dict) -> Dict:
        self._client_config.update(config)
        with open(self.client_config_file, "w", encoding="utf-8") as f:
            json.dump(self._client_config, f, ensure_ascii=False, indent=2)
        return self._client_config

    def _save_apis(self):
        with open(self.api_configs_file, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._api_configs.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _save_prompts(self):
        with open(self.prompt_configs_file, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._prompt_configs.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _save_mineru(self):
        with open(self.mineru_configs_file, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._mineru_configs.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _save_current_api(self):
        with open(self.current_api_file, "w", encoding="utf-8") as f:
            json.dump({"current_api_id": self._current_api_id}, f)

    def _save_current_mineru(self):
        with open(self.current_mineru_file, "w", encoding="utf-8") as f:
            json.dump({"current_mineru_id": self._current_mineru_id}, f)

    def add_api_config(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        is_default: bool = False,
    ) -> APIConfig:
        config_id = str(uuid.uuid4())[:8]
        config = APIConfig(
            id=config_id,
            name=name,
            base_url=base_url,
            api_key=api_key,
            model=model,
            is_default=is_default,
        )
        self._api_configs[config_id] = config
        if is_default or not self._current_api_id:
            self._current_api_id = config_id
        self._save_apis()
        self._save_current_api()
        return config

    def update_api_config(self, config_id: str, **kwargs) -> Optional[APIConfig]:
        if config_id not in self._api_configs:
            return None
        config = self._api_configs[config_id]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self._save_apis()
        return config

    def delete_api_config(self, config_id: str) -> bool:
        if config_id in self._api_configs:
            del self._api_configs[config_id]
            if self._current_api_id == config_id:
                self._current_api_id = (
                    next(iter(self._api_configs), None) if self._api_configs else None
                )
            self._save_apis()
            self._save_current_api()
            return True
        return False

    def get_api_configs(self) -> List[APIConfig]:
        return list(self._api_configs.values())

    def get_api_config(self, config_id: str) -> Optional[APIConfig]:
        return self._api_configs.get(config_id)

    def get_current_api(self) -> Optional[APIConfig]:
        return (
            self._api_configs.get(self._current_api_id)
            if self._current_api_id
            else None
        )

    def set_current_api(self, config_id: str) -> bool:
        if config_id in self._api_configs:
            self._current_api_id = config_id
            self._save_current_api()
            return True
        return False

    def add_mineru_config(
        self, name: str, token: str, is_default: bool = False
    ) -> MinerUConfig:
        config_id = str(uuid.uuid4())[:8]
        config = MinerUConfig(
            id=config_id,
            name=name,
            token=token,
            is_default=is_default,
        )
        self._mineru_configs[config_id] = config
        if is_default or not self._current_mineru_id:
            self._current_mineru_id = config_id
        self._save_mineru()
        self._save_current_mineru()
        return config

    def update_mineru_config(self, config_id: str, **kwargs) -> Optional[MinerUConfig]:
        if config_id not in self._mineru_configs:
            return None
        config = self._mineru_configs[config_id]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self._save_mineru()
        return config

    def delete_mineru_config(self, config_id: str) -> bool:
        if config_id in self._mineru_configs:
            del self._mineru_configs[config_id]
            if self._current_mineru_id == config_id:
                self._current_mineru_id = (
                    next(iter(self._mineru_configs), None)
                    if self._mineru_configs
                    else None
                )
            self._save_mineru()
            self._save_current_mineru()
            return True
        return False

    def get_mineru_configs(self) -> List[MinerUConfig]:
        return list(self._mineru_configs.values())

    def get_mineru_config(self, config_id: str) -> Optional[MinerUConfig]:
        return self._mineru_configs.get(config_id)

    def get_current_mineru(self) -> Optional[MinerUConfig]:
        return (
            self._mineru_configs.get(self._current_mineru_id)
            if self._current_mineru_id
            else None
        )

    def set_current_mineru(self, config_id: str) -> bool:
        if config_id in self._mineru_configs:
            self._current_mineru_id = config_id
            self._save_current_mineru()
            return True
        return False

    def add_prompt_config(
        self, name: str, prompt: str, is_enabled: bool = True
    ) -> PromptConfig:
        config_id = str(uuid.uuid4())[:8]
        config = PromptConfig(
            id=config_id, name=name, prompt=prompt, is_enabled=is_enabled
        )
        self._prompt_configs[config_id] = config
        self._save_prompts()
        return config

    def update_prompt_config(self, config_id: str, **kwargs) -> Optional[PromptConfig]:
        if config_id not in self._prompt_configs:
            return None
        config = self._prompt_configs[config_id]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self._save_prompts()
        return config

    def delete_prompt_config(self, config_id: str) -> bool:
        if config_id in self._prompt_configs:
            del self._prompt_configs[config_id]
            self._save_prompts()
            return True
        return False

    def get_prompt_configs(self, enabled_only: bool = False) -> List[PromptConfig]:
        prompts = list(self._prompt_configs.values())
        if enabled_only:
            prompts = [p for p in prompts if p.is_enabled]
        return prompts

    def get_prompt_config(self, config_id: str) -> Optional[PromptConfig]:
        return self._prompt_configs.get(config_id)
