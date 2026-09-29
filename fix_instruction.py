with open("a2ui_system_prompt.txt") as f:
    prompt = f.read()

with open("app/agent.py") as f:
    code = f.read()

# Replace the broken SYSTEM_INSTRUCTION
start_marker = "SYSTEM_INSTRUCTION = "
end_marker = "root_agent = Agent("

idx_start = code.find(start_marker)
idx_end = code.find(end_marker)

if idx_start != -1 and idx_end != -1:
    before = code[:idx_start]
    after = code[idx_end:]
    # Safely write prompt into a separate file or assign via triple-quotes
    new_code = before + "SYSTEM_INSTRUCTION = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'a2ui_system_prompt.txt')).read()\n\n" + after
    with open("app/agent.py", "w") as f:
        f.write(new_code)
    print("Fixed SYSTEM_INSTRUCTION assignment in app/agent.py!")
else:
    print("Markers not found!")
