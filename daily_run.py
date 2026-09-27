import os
import datetime
from news_agent import get_top_ai_news

def main():
    print("JARVIS Daily Agent: Initializing...")
    
    # Check if API key exists in GitHub Secrets environment
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set in environment variables.")
        print("Please add it to your GitHub Repository Secrets.")
        return

    print("Fetching top AI news from global RSS feeds...")
    try:
        # Re-use our existing logic to fetch the top 10 articles
        news_items = get_top_ai_news(count=10)
    except Exception as e:
        print(f"Error fetching news: {e}")
        return

    if not news_items:
        print("No news articles found today.")
        return

    # Generate Markdown Report
    date_str = datetime.datetime.now().strftime("%B %d, %Y")
    
    markdown = f"# JARVIS Daily AI Intelligence Report\n\n"
    markdown += f"**Date:** {date_str}\n\n"
    markdown += "---\n\n"
    
    for idx, item in enumerate(news_items, 1):
        markdown += f"### {idx}. [{item['title']}]({item['link']})\n"
        markdown += f"**Source:** {item['source']} | **Published:** {item['published']}\n\n"
        # We don't include the full summary in the markdown if it's too long, but we can include a short snippet
        markdown += f"{item.get('summary', 'No summary available.')[:300]}...\n\n"
    
    # Write to file
    with open("daily_news.md", "w", encoding="utf-8") as f:
        f.write(markdown)
        
    print("JARVIS Daily Agent: Successfully generated daily_news.md")

if __name__ == "__main__":
    main()
