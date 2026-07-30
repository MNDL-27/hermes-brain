import sys
import types

# Stub out the Hermes runtime — not installed in dev env.
# Do NOT stub notion_brain; the tests import from it directly.
for mod_name in ['agent', 'agent.memory_manager', 'agent.memory_provider', 'tools', 'tools.registry']:
    if mod_name not in sys.modules:
        mod = types.ModuleType(mod_name)
        if mod_name == 'agent.memory_manager':
            setattr(mod, 'sanitize_context', lambda x: x)
        elif mod_name == 'agent.memory_provider':
            setattr(mod, 'MemoryProvider', type('MemoryProvider', (), {}))
        elif mod_name == 'tools.registry':
            setattr(mod, 'tool_error', lambda x: 'error: ' + str(x))
        sys.modules[mod_name] = mod
