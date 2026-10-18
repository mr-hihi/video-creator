# Template — API endpoint

```python
# service.py — rules only
def rename_job(self, job_id: str, new_name: str) -> Job:
    job = self.get_job(job_id)
    if not new_name.strip():
        raise InvalidRenameError("Name must not be blank")
    return self._repository.rename(job.id, new_name.strip())


# errors.py
class InvalidRenameError(Exception):
    pass


# http_errors.py — add one row
STATUS_CODES_BY_ERROR = {..., InvalidRenameError: status.HTTP_400_BAD_REQUEST}


# schemas.py — request DTO next to the response DTOs
class RenameJobRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    new_name: str


# router.py — HTTP only
@router.patch("/{job_id}", dependencies=[Depends(require_captcha)])
def rename_job(job_id: str, body: RenameJobRequest, service: JobServiceDependency) -> JobResponse:
    return JobResponse.model_validate(service.rename_job(job_id, body.new_name))
```

```python
# tests/test_router.py — fixture acts, test asserts
@pytest.fixture
def blank_rename_response(client, job_service):
    job_service.rename_job.side_effect = InvalidRenameError("Name must not be blank")
    return client.patch(f"/jobs/{JOB_ID}", json={"newName": " "}, headers=CAPTCHA_HEADERS)


def test_rename_job_answers_400_on_blank_name(blank_rename_response):
    assert blank_rename_response.status_code == 400
```
