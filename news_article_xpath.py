import asyncio
import os
import pprint
import re

import requests
import tiktoken
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from lxml import etree, html
from openai import OpenAI
from playwright.async_api import async_playwright

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI LLM
llm = OpenAI()


def remove_script_tags(html_content):
    # Parse HTML content
    tree = html.fromstring(html_content)

    # Remove script tags
    etree.strip_elements(tree, "script")

    # Serialize the modified HTML content
    cleaned_html = html.tostring(tree, method="html", encoding=str)

    return cleaned_html


def remove_css_script(css_content):
    # Parse CSS content
    tree = html.fromstring(css_content)

    # Remove script elements (if any)
    for element in tree.xpath("//script"):
        element.getparent().remove(element)

    # Serialize the modified CSS content
    cleaned_css = etree.tostring(tree, encoding=str)

    return cleaned_css


class ScrapePlaywright:
    def __init__(self, url: str, gpt_model: str):
        self.url = url
        self.gpt_model = gpt_model
        self.encoding = tiktoken.encoding_for_model(self.gpt_model)

    async def run(self) -> str:
        """
        An asynchronous Python function that uses Playwright to scrape
        content from a given URL, extracting specified HTML tags and removing unwanted tags and unnecessary
        lines.

        Additionally, the function uses OpenAI's GPT-3 model to generate XPath expressions for extracting
        specific information from the scraped content.
        """
        print("Started scraping...")
        page_source = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            try:
                page = await browser.new_page()
                await page.goto(self.url)

                page_source_html = await page.content()

                xpath_href_dashboard_page = []
                # TODO: Save the href for the news article page to the yaml file
                for chunk in self.trim_to_encoder_size_generator(page_source_html):
                    xpath_href_dashboard_page = self.generate_xpath(
                        chunk,
                        (
                            "Using the following HTML chunk,"
                            " extract each @href item link within"
                            " the news page,"
                            " extracting the @href attribute that"
                            " links to the article itself, ONLY.",
                        ),
                    )

                    if xpath_href_dashboard_page == "":
                        raise Exception(
                            "No XPath expression generated for the href attribute"
                        )
                    print(
                        f"XPath generated by {self.gpt_model}",
                        xpath_href_dashboard_page.split("\n")[0],
                    )

                    next_url = html.fromstring(page_source_html).xpath(
                        xpath_href_dashboard_page.split("\n")[0]
                    )
                    print(next_url)
                    try:
                        import pdb

                        pdb.set_trace()
                        # Go to the news article page
                        await page.click(next_url)
                        break
                    except Exception as e:
                        print(e)
                        continue

                # Get the page source
                page_source = await page.content()

                ## Generate xpaths
                print("Content scraped")
            except Exception as e:
                raise e
            await browser.close()
        return page_source

    # Define a function to generate XPath expressions using LLM
    def generate_xpath(self, html_content, target_info):
        prompt = (
            f"Given the HTML content:\n\n```html\n{html_content}\n```"
            f"\n\nExtract the following information using XPath: {target_info}"
            " in the format \n\nXPath: ```xpath\n//xpath/expression\n```\n\n"
        )

        completion = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        ).chat.completions.create(
            model=self.gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Web Developer with extensive knowledge of HTML, CSS, Javascript, etc. You are tasked with extracting specific information from a webpage using XPath.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        choice = None
        assert isinstance(completion.choices, list), "No choices returned"
        choice = completion.choices[0]
        assert choice != None, "No choice returned"
        assert choice.message != None, "No message in choice"
        assert choice.message.content != None, "No content in message"
        assert (
            "```xpath" in choice.message.content
        ), "No parsable xpath expression returned"

        xpath_expr = re.sub(
            "```", "", choice.message.content.split("```xpath")[1]
        ).strip()

        assert xpath_expr != None, "No xpath expression returned"

        return xpath_expr

    def trim_to_encoder_size_generator(self, html, chunk_size=8192):
        """
        Trims the text to the maximum length that can be processed by the encoder.
        """
        # TODO: try to trim a little bit more accurately to account for the input prompt + the generation tokens
        EXTRA_PROMPT_OR_GENERATION_TOKENS = 160

        html_encoded = self.encoding.encode(html)
        if (
            len(self.encoding.encode(html))
            > chunk_size - EXTRA_PROMPT_OR_GENERATION_TOKENS
        ):
            for i in range(0, len(html_encoded), chunk_size):
                yield self.encoding.decode(
                    html_encoded[i : i + chunk_size - EXTRA_PROMPT_OR_GENERATION_TOKENS]
                )

        yield html


# Define a function to extract data using XPath expressions
def extract_data(html_content, xpaths):
    tree = html.fromstring(html_content)
    extracted_data = {}
    for key, xpath in xpaths.items():
        extracted_data[key] = tree.xpath(xpath)
    return extracted_data


if __name__ == "__main__":

    result = asyncio.run(
        ScrapePlaywright(
            "https://valneva.com/media/press-releases/",
            gpt_model="gpt-4",
        ).run()
    )
    import pdb

    pdb.set_trace()

    cleaned_html = remove_script_tags(result)
    _cleaned_html = remove_css_script(cleaned_html)

    # Example usage
    xpath_title = generate_xpath(llm, _result, "Title")
    xpath_date = generate_xpath(llm, _result, "Date")
    xpath_description = generate_xpath(llm, _result, "Description")

    import pdb

    pdb.set_trace()
    xpaths = {
        "title": xpath_title,
        "date": xpath_date,
        "description": xpath_description,
    }
    dashboard_chain = NewsDashboardChain(llm)
    news_article_chain = NewsArticleChain(llm)

    # Extracting article links from a news dashboard
    dashboard_url = "https://valneva.com/media/press-releases/"
    article_links = dashboard_chain.run(dashboard_url)
    print(article_links)

    # Extracting data from a news article page
    article_url = "https://example.com/news-article"
    article_data = news_article_chain.run(article_url)
    print(article_data)
