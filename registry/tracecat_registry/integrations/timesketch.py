"""Timesketch integration with S3, Sigma rules, and additional features.

Authentication method: API Token

Requires: 
- A secret named `timesketch` with the following keys:
    - `TS_HOST`
    - `TS_API_TOKEN`
- A secret named `aws` with the following keys:
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_REGION`
"""

import json
from typing import Annotated, Any, List, Optional
from pydantic import Field
from timesketch_api_client import client
import aioboto3
from tracecat_registry import RegistrySecret, registry, secrets

timesketch_secret = RegistrySecret(
    name="timesketch",
    keys=["TS_HOST", "TS_API_TOKEN"],
)
"""Timesketch secret.

- name: `timesketch`
- keys:
    - `TS_HOST`
    - `TS_API_TOKEN`
"""

aws_secret = RegistrySecret(
    name="aws",
    keys=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"],
)
"""AWS secret.

- name: `aws`
- keys:
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_REGION`
"""


class TimesketchClient:
    def __init__(self, host: str, api_token: str):
        self.host = host
        self.api_token = api_token
        self._client = client.TimesketchApi(host, api_token)

    def create_timeline(self, name: str, description: Optional[str] = None) -> Any:
        sketch = self._client.create_sketch(name=name, description=description)
        return {"sketch_id": sketch.id, "name": name, "description": description}

    def upload_data(
        self,
        sketch_id: int,
        data: List[dict],
        timeline_name: str,
        timestamp_field: str = "timestamp",
    ) -> Any:
        sketch = self._client.get_sketch(sketch_id)
        timeline = sketch.upload(data, timeline_name, timestamp_field)
        return {"timeline_id": timeline.id, "name": timeline_name}

    def search_timeline(
        self, sketch_id: int, query: str, query_filter: Optional[dict] = None
    ) -> List[dict]:
        sketch = self._client.get_sketch(sketch_id)
        result = sketch.explore(query=query, query_filter=query_filter)
        return [entry.to_dict() for entry in result]

    def manage_sigma_rule(
        self,
        sketch_id: int,
        action: str,
        rule_id: Optional[int] = None,
        rule_content: Optional[dict] = None,
    ) -> Any:
        sketch = self._client.get_sketch(sketch_id)
        sigma = sketch.sigma

        if action == "list":
            return [rule.to_dict() for rule in sigma.list()]
        elif action == "get" and rule_id:
            return sigma.get(rule_id).to_dict()
        elif action == "create" and rule_content:
            return sigma.create(rule_content).to_dict()
        elif action == "delete" and rule_id:
            sigma.delete(rule_id)
            return {"status": "deleted", "rule_id": rule_id}
        else:
            raise ValueError("Invalid Sigma rule operation or missing parameters.")

    def run_saved_search_by_name(self, sketch_id: int, search_name: str) -> List[dict]:
        sketch = self._client.get_sketch(sketch_id)
        saved_searches = sketch.list_saved_searches()

        # Find the saved search by name
        saved_search = next(
            (search for search in saved_searches if search.name == search_name), None
        )
        if not saved_search:
            raise ValueError(f"Saved search with name '{search_name}' not found.")

        result = saved_search.query.run()
        return [entry.to_dict() for entry in result]

    def tag_event(
        self, sketch_id: int, timeline_id: int, event_id: str, tags: List[str]
    ) -> dict:
        sketch = self._client.get_sketch(sketch_id)
        event = sketch.get_event(timeline_id, event_id)
        event.add_tags(tags)
        event.commit()
        return {"event_id": event_id, "tags": tags}


async def fetch_data_from_s3(s3_url: str) -> List[dict]:
    """Fetch data from S3 bucket."""
    import urllib.parse

    parsed_url = urllib.parse.urlparse(s3_url)
    bucket = parsed_url.netloc
    key = parsed_url.path.lstrip("/")

    session = aioboto3.Session(
        aws_access_key_id=secrets.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=secrets.get("AWS_SECRET_ACCESS_KEY"),
        region_name=secrets.get("AWS_REGION"),
    )

    async with session.client("s3") as s3_client:
        response = await s3_client.get_object(Bucket=bucket, Key=key)
        data = await response["Body"].read()
        return json.loads(data)


def create_timesketch_client() -> TimesketchClient:
    client = TimesketchClient(
        host=secrets.get("TS_HOST"),
        api_token=secrets.get("TS_API_TOKEN"),
    )
    return client


@registry.register(
    default_title="Run Saved Search by Name",
    description="Run a saved search by name in Timesketch",
    display_group="Timesketch",
    namespace="integrations.timesketch",
    secrets=[timesketch_secret],
)
def run_saved_search_by_name(
    sketch_id: Annotated[int, Field(..., description="Sketch ID")],
    search_name: Annotated[str, Field(..., description="Saved search name")],
) -> List[dict[str, Any]]:
    client = create_timesketch_client()
    results = client.run_saved_search_by_name(sketch_id=sketch_id, search_name=search_name)
    return results


@registry.register(
    default_title="Tag an Event",
    description="Add tags to an event in Timesketch",
    display_group="Timesketch",
    namespace="integrations.timesketch",
    secrets=[timesketch_secret],
)
def tag_event_in_timesketch(
    sketch_id: Annotated[int, Field(..., description="Sketch ID")],
    timeline_id: Annotated[int, Field(..., description="Timeline ID")],
    event_id: Annotated[str, Field(..., description="Event ID")],
    tags: Annotated[List[str], Field(..., description="List of tags to add")],
) -> dict[str, Any]:
    client = create_timesketch_client()
    result = client.tag_event(sketch_id=sketch_id, timeline_id=timeline_id, event_id=event_id, tags=tags)
    return result


@registry.register(
    default_title="Upload Data from S3 to Timesketch",
    description="Upload data from an S3 bucket to a Timesketch timeline",
    display_group="Timesketch",
    namespace="integrations.timesketch",
    secrets=[timesketch_secret, aws_secret],
)
async def upload_data_from_s3_to_timesketch(
    sketch_id: Annotated[int, Field(..., description="Sketch ID")],
    s3_url: Annotated[str, Field(..., description="S3 URL of the data")],
    timeline_name: Annotated[str, Field(..., description="Name of the timeline")],
    timestamp_field: Annotated[
        str,
        Field(
            ..., description="Field in the data to use as the timestamp (e.g., 'timestamp')"
        ),
    ] = "timestamp",
) -> dict[str, Any]:
    """Fetch data from S3 and upload to Timesketch."""
    data = await fetch_data_from_s3(s3_url)
    client = create_timesketch_client()
    result = client.upload_data(
        sketch_id=sketch_id,
        data=data,
        timeline_name=timeline_name,
        timestamp_field=timestamp_field,
    )
    return result