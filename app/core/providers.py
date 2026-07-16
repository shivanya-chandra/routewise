def provider_from_model_name(model: str) -> str | None:
    if "/" in model:
        provider, _model_name = model.split("/", 1)
        return provider or None

    if model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")):
        return "openai"

    return None


def required_env_var_for_provider(provider: str | None) -> str | None:
    if provider == "openai":
        return "OPENAI_API_KEY"

    return None
