# Till Ecosystem 🌳

*A personal finance assistant designed to make tracking money more convenient, less anxiety-inducing, and maybe even… a little whimsical. 
The name “Till” comes from both money tills **and** tilling the land for future harvests.*

## The Forest 🌿

**🍄 Mycelium Till** *(Cloud/Railway)*  
The always-ready collector. Receives your messages about expenses and earnings via Telegram, stores them in the cloud, and waits patiently for Tree Till to process everything. Simple & reliable.

**🌳 Tree Till** *(Local/Laptop)*  
The wise accountant. Recruits Gemma3n for intelligent transaction categorization, manages your complete financial picture (assets.db), and processes the mycelium's collected nutrients into organized financial wisdom.

**🌿 Dapple Till** *(Local/Conversational)*  
The poetic advisor. Responds to your financial questions with data-driven poems followed by three thoughtful questions to guide your research and reflection. Knows your complete financial context. Nerdy Magic 8 Ball meets pragmatic fortune cookie. 

## Architecture 

```
📱 Text "Coffee $5.50" to Telegram
    ↓
🍄 Mycelium Till (Railway Cloud)
    ↓ stores raw messages  
☁️  Simple Database (just messages)
    ↓ syncs when laptop online
💻 Tree Till (Local Laptop + Gemma3n)
    ↓ processes, categorizes, advises
🗄️  Rich Local Database (your financial brain)
    ↓ context for conversations
🌿 Dapple Till (Local Interaction)
```

## Privacy-First Design

- **Your data stays yours**: All personal financial information lives on your laptop
- **Cloud only collects**: Railway just temporarily stores raw messages until processing  
- **AI runs locally**: Gemma3n categorization happens on your machine
- **No financial data in git**: Database files are gitignored for your privacy

## The Vision

Till is about motivation through wit + wisdom -- relief against the stress and shame that usually come with money talk. The three practical questions after each poem serve to point the user in the right direction for further research and reflection. The goal is to blend playfulness with rigor. 🌱
