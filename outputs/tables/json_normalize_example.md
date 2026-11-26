# json_normalize: before and after

**Before** — one YouTube comment as the API returns it (nested JSON, author fields redacted here):

```json
{
  "kind": "youtube#commentThread",
  "etag": "h9O7giyHd6XQ70KussX408pkSFQ",
  "id": "UgwLNmu97etBx5gNP5N4AaABAg",
  "snippet": {
    "videoId": "77vRyWNqZjM",
    "topLevelComment": {
      "kind": "youtube#comment",
      "etag": "I3Z3YFaMN80wWsCGapvn5_Jda1w",
      "id": "UgwLNmu97etBx5gNP5N4AaABAg",
      "snippet": {
        "channelId": "UC-LOdiPoxninevJ0DkleCLg",
        "videoId": "77vRyWNqZjM",
        "textDisplay": "We need more and more and more films like this please please",
        "textOriginal": "We need more and more and more films like this please please",
        "authorDisplayName": "«removed for privacy»",
        "authorProfileImageUrl": "«removed for privacy»",
        "authorChannelUrl": "«removed for privacy»",
        "authorChannelId": "«removed for privacy»",
        "canRate": true,
        "viewerRating": "none",
        "likeCount": 1,
        "publishedAt": "2026-11-11T07:39:14Z",
        "updatedAt": "2026-11-11T07:39:14Z"
      }
    },
    "canReply": true,
    "totalReplyCount": 0,
    "isPublic": true
  }
}
```

**After** — the same comment as one flat row (author columns dropped entirely):

| film_id   | comment_id                 | youtube_video_id   | published_ts_raw     | text_raw                                                     |   like_count |   reply_count |
|:----------|:---------------------------|:-------------------|:---------------------|:-------------------------------------------------------------|-------------:|--------------:|
| chhaava   | UgwLNmu97etBx5gNP5N4AaABAg | 77vRyWNqZjM        | 2026-11-11T07:39:14Z | We need more and more and more films like this please please |            1 |             0 |
