from airflow.decorators import dag, task
import pendulum
import requests
import xmltodict
import logging
import os
from datetime import timedelta
from airflow.providers.sqlite.operators.sqlite import SqliteOperator
from airflow.providers.sqlite.hooks.sqlite import SqliteHook

@dag(
    dag_id="podcast_summery",
    schedule_interval='@daily',
    start_date=pendulum.datetime(2023,11,18),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
)
def podcast_summery():
    create_database = SqliteOperator(
        task_id="create_table_sqlite",
        sql=r"""
        CREATE TABLE IF NOT EXISTS episodes(
            link TEXT PRIMARY KEY,
            title TEXT,
            filename TEXT,
            published TEXT,
            description TEXT
        )
        """,
        sqlite_conn_id="podcasts",
    )

    @task()
    def get_episode():
        data = requests.get("https://marketplace.org/feed/podcast/marketplace")
        feed = xmltodict.parse(data.text)
        episodes = feed["rss"]["channel"]["item"]
        print(f"Found {len(episodes)} episodes.")
        return episodes



    # Define the tasks using @task and set dependencies using >>
    podcast_episodes = get_episode()
    create_database >> podcast_episodes

    @task()
    def load_episode(episodes):
        hook=SqliteHook(sqlite_conn_id="podcasts")
        stored=hook.get_pandas_df("SELECT * FROM episodes;")
        new_episodes=[]
        for episode in episodes:
            if episode["link"] not in stored["link"].values:
                filename=f"{episode['link'].split('/')[-1]}.mp3"
                new_episodes.append([episode["link"], episode['title'], episode['pubDate'], episode['description'], filename])
        hook.insert_rows(table="episodes", rows=new_episodes, target_fields=["link", "title", "published", "description", "filename"])

    load_episode(podcast_episodes)

    @task()
    def download_episodes(episodes):
        for episode in episodes:
            filename=f"{episode['link'].split('/')[-1]}.mp3"
            audio_path=os.path.join("episodes", filename)
            print(f"{audio_path}")
            if not os.path.exists("./episodes"):
                os.mkdir("episodes")
            
            if not os.path.exists(audio_path):
                print(f"Downloading {filename}")
                audio=requests.get(episode["enclosure"]["@url"])
                with open (audio_path, "wb+") as f: 
                    f.write(audio.content)
    
    download_episodes(podcast_episodes)

# Create the DAG instance
summery = podcast_summery()
