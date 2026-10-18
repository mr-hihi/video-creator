# Template — module skeleton (router → service → repository)

```
app/modules/<module>/
├── models.py        # SQLAlchemy model(s) + StrEnums
├── repository.py    # SQL only, one short session per method
├── service.py       # rules; raises errors.py types
├── schemas.py       # response DTOs (camelCase)
├── errors.py        # domain errors
├── http_errors.py   # error → status table + register_<module>_error_handlers(app)
└── router.py        # HTTP only
```

```python
# repository.py
class WidgetRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def find_by_id(self, widget_id: str) -> Widget | None:
        with self._session_factory() as session:
            return session.get(Widget, widget_id)


# service.py
class WidgetService:
    def __init__(self, repository: WidgetRepository):
        self._repository = repository

    def get_widget(self, widget_id: str) -> Widget:
        widget = self._repository.find_by_id(widget_id)
        if widget is None:
            raise WidgetNotFoundError(widget_id)
        return widget


# router.py
router = APIRouter(prefix="/widgets", tags=["widgets"])


def get_widget_service(request: Request) -> WidgetService:
    return request.app.state.container.widget_service


WidgetServiceDependency = Annotated[WidgetService, Depends(get_widget_service)]


@router.get("/{widget_id}")
def get_widget(widget_id: str, service: WidgetServiceDependency) -> WidgetResponse:
    return WidgetResponse.model_validate(service.get_widget(widget_id))
```
