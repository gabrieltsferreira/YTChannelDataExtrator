from googleapiclient.discovery import build
import pandas as pd
import isodate 
import datetime
import ast
from config import api_key, api_service_name, api_version

# Get credentials and create an API client
youtube = build(api_service_name, api_version, developerKey=api_key)

# Get channel info
def get_channel_info(channel_id):
        request = youtube.channels().list(
                part='snippet,contentDetails,statistics',
                id=channel_id
        )
        response = request.execute()

        data = {'channel_name': response['items'][0]['snippet']['title'],
                'subscribers': response['items'][0]['statistics']['subscriberCount'],
                'total_views': response['items'][0]['statistics']['viewCount'],
                'videos_count': response['items'][0]['statistics']['videoCount'],
                'playlist_uploads_id': response['items'][0]['contentDetails']['relatedPlaylists']['uploads'],
                'profile_pic_url': response['items'][0]['snippet']['thumbnails']['default']['url'],
                'country': response['items'][0]['snippet']['country'] if 'country' in response['items'][0]['snippet'] else '-'        
        }

        return data

#----//----//----//----//----//----//----//----//----//----//----//----//----//----//

# Get videos from playlist
def get_video_ids(playlist_id, videos_count):
        video_ids = []

        request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                maxResults=50,
                playlistId=playlist_id
        )
        response = request.execute()

        for item in response['items']:
                video_ids.append(item['contentDetails']['videoId'])


        # Get next page results
        token = ''
        while token != None and int(videos_count)>50:
                request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                maxResults=50,
                playlistId=playlist_id,
                pageToken=response.get('nextPageToken')
                )
                response = request.execute()

                for item in response['items']:
                        video_ids.append(item['contentDetails']['videoId'])

                token = response.get('nextPageToken')
        
        return video_ids

#----//----//----//----//----//----//----//----//----//----//----//----//----//----//

# Get video info by ID
def get_video_info(video_ids):
        all_videos_info = []

        for i in range(0, len(video_ids), 50):
                request = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_ids[i:i+50]
                )
                response = request.execute()

                for video in response['items']:
                        info = {'video_id': video['id'],   
                                # info                            
                                'channelTitle': video['snippet']['channelTitle'], 
                                'title': video['snippet']['title'], 
                                'description': video['snippet']['description'], 
                                'tags': video['snippet']['tags'] if 'tags' in video['snippet'] else None,
                                'publishedAt': video['snippet']['publishedAt'],
                                'thumbnail_url': video['snippet']['thumbnails']['default']['url'],

                                # statistics
                                'viewCount': video['statistics']['viewCount'],
                                'likeCount': video['statistics']['likeCount'] if 'likeCount' in video['statistics'] else 0,
                                'favoriteCount': video['statistics']['favoriteCount'],
                                'commentCount': video['statistics']['commentCount'] if 'commentCount' in video['statistics'] else 0,

                                # content details
                                'duration': video['contentDetails']['duration'],
                                'definition': video['contentDetails']['definition'], 
                        }

                        all_videos_info.append(info)

        return all_videos_info



#----//----//----//----//----//----//----//----//----//----//----//----//----//----//

# Get comments by video ID
def get_all_comments(video_ids):
        all_comments = []

        for video_id in video_ids:
                request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id
                )
                response = request.execute()
                comments = []
                for item in response['items']:
                        comments.append(item['snippet']['topLevelComment']['snippet']['textOriginal'])

                comments_in_video = {
                        'video_id': video_id,
                        'comments': comments
                }

                all_comments.append(comments_in_video)

        return all_comments

#----//----//----//----//----//----//----//----//----//----//----//----//----//----//

# comments = get_all_comments(video_ids)
# print(pd.DataFrame(comments))

def get_channel_stats(channel_id):
        channel_info = get_channel_info(channel_id)

        video_ids = get_video_ids(channel_info['playlist_uploads_id'], channel_info['videos_count'])

        video_info = get_video_info(video_ids)

        df = pd.DataFrame(video_info)

        # Converting numeric cols to int   
        numeric_cols = ['viewCount', 'likeCount', 'favoriteCount', 'commentCount']
        df[numeric_cols] = df[numeric_cols].astype(int)

        # Converting date col to date type
        df['publishedAt'] = pd.to_datetime(df['publishedAt'])

        # Converting video duration values from ISO
        df['duration'] = df['duration'].apply(lambda x: isodate.parse_duration(x).total_seconds())

        # Creating CSV File
        df.to_csv('output/download.csv', encoding='utf-8', index=False)


        # Insights -------------//-------------//-------------//-------------//
        insights = {}

        # TOTAL LIKES -------------//-------------//-------------//
        insights['total_likes'] = int(df['likeCount'].sum())


        # UPLOADS -------------//-------------//-------------//

        total_uploads = df['video_id'].count()

        last_post_day = df['publishedAt'][0]
        first_post_day = df['publishedAt'].iloc[-1]

        delta = last_post_day - first_post_day

        # Uploads per Month
        n_months = delta.days/30
        insights['avg_uploads_per_month'] = total_uploads/n_months

        # Uploads per Week
        n_weeks = delta.days/7
        insights['avg_uploads_per_week'] = total_uploads/n_weeks

        # Uploads per Day
        n_days = delta.days
        insights['avg_uploads_per_day'] = total_uploads/n_days


        # AVG METRICS -------------//-------------//-------------//

        # avg views/video
        insights['avg_views_per_video'] = df['viewCount'].median()

        # avg likes/vieo
        insights['avg_likes_per_video'] = df['likeCount'].median()

        # avg comments/video
        insights['avg_comments_per_video'] = df['commentCount'].median()

        # avg video duration
        insights['avg_video_duration'] = df['duration'].median()


        # TOP 10 HASHTAGS -------------//-------------//-------------//

        all_tags = []

        for tag_group in df[df['tags'].notna()]['tags']:
                if tag_group:
                        all_tags.append(ast.literal_eval(str(tag_group)))    


        flat_list = [item for sublist in all_tags for item in sublist]

        top_hashtags = pd.Series(flat_list).value_counts()[:10].index.tolist()

        insights['top_hashtags'] = top_hashtags


        # TOP VIDEOS -------------//-------------//-------------//


        # Week Days Upload distribution -------------//-------------//-------------//
        weekdays_dist = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}

        for dates in df['publishedAt']:
                match dates.weekday():
                        case 0:
                                weekdays_dist['Monday'] = weekdays_dist['Monday'] + 1     
                        case 1:
                                weekdays_dist['Tuesday'] = weekdays_dist['Tuesday'] + 1
                        case 2:
                                weekdays_dist['Wednesday'] = weekdays_dist['Wednesday'] + 1
                        case 3:
                                weekdays_dist['Thursday'] = weekdays_dist['Thursday'] + 1
                        case 4:
                                weekdays_dist['Friday'] = weekdays_dist['Friday'] + 1
                        case 5:
                                weekdays_dist['Saturday'] = weekdays_dist['Saturday'] + 1
                        case 6:
                                weekdays_dist['Sunday'] = weekdays_dist['Sunday'] + 1

        insights['weekdays_dist'] = weekdays_dist


        # Week Days Upload distribution -------------//-------------//-------------//
        dates = []
        times = []

        for date_time in df['publishedAt']:
                dates.append(date_time.strftime('%Y-%m-%d'))
                times.append(date_time.strftime('%H:%M'))
        
        dates.reverse()
        times.reverse()

        insights['dates'] = dates
        insights['times'] = times
        




        return channel_info, insights