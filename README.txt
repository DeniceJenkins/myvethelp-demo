MYVETHELP DEMO — HOW TO RUN IT
=============================

WHAT'S IN THIS FOLDER
- app.py                             -> the demo app itself
- MyVetHelp_Resource_Database.xlsx     -> the resource data it reads from

STEP 1 — Install the free tools it needs (one time only)
Open a terminal / command prompt and type:

    pip install streamlit openpyxl pandas openai

STEP 2 — Run the app
In the same terminal, make sure you're in this folder, then type:

    streamlit run app.py

A browser tab will open automatically showing the app.

STEP 3 — Try it
Type something like:
    "I don't know how to file for disability benefits"
    "I need help with school and the GI bill"
    "I am homeless and need housing"

The app will show the closest-matching resource(s) from the spreadsheet.

UPDATING THE RESOURCE LIST
Just edit MyVetHelp_Resource_Database.xlsx directly (add rows in the same
format), save it, and re-run the app — no code changes needed.

TURNING ON AI-PHRASED ANSWERS (OPTIONAL)
By default, the app just shows the matched resource directly — no AI
key needed, and this works fine for a demo on its own.

If you want the AI to write a friendlier, conversational answer instead,
you'll need three things from your school's Azure OpenAI setup:
  1. Endpoint        — looks like https://your-resource-name.openai.azure.com/
  2. API key
  3. Deployment name — the name given to the model when it was deployed
                        in Azure AI Foundry / Azure OpenAI Studio (e.g. "gpt-4o")

Once the app is running, there's a small "AI Phrasing (optional)" panel
in the left sidebar. Paste those three values in there — the app will
immediately start using AI to phrase answers. Leave them blank and it
just works the plain way, no code changes needed either way.

If nobody in your group has generated an Azure OpenAI deployment yet,
that's a separate one-time setup step in the Azure Portal / Azure AI
Foundry — ask if you want help walking through that next.
