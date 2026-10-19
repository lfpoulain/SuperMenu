"""Provider-specific payloads, probes and response parsing for OpenAIClient.

These modules never open a session of their own: the client passes the pooled
session of ``supermenu_core.api.openai_client`` so every request keeps sharing
one connection pool. They never import ``openai_client`` either.
"""
