from typing import Optional, Sequence

from admin_extra_buttons.decorators import button, view
from admin_extra_buttons.mixins import ExtraButtonsMixin
from django.contrib import admin, messages
from django.db.models import Model
from django.forms import Media
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from celery_model.models import CeleryTaskModel


class CeleryTaskModelAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    def get_readonly_fields(self, request: HttpRequest, obj: "Optional[Model]" = None) -> Sequence[str]:
        ret = list(super().get_readonly_fields(request, obj))
        ret.append("curr_async_result_id")
        return ret

    def check(self, **kwargs):
        return []

    @button()
    def check_status(self, request: HttpRequest) -> "HttpResponse":  # type: ignore
        obj: CeleryTaskModel
        for obj in self.get_queryset(request):
            if obj.async_result is None:
                obj.curr_async_result_id = None
                obj.save()

    @view()
    def celery_discard_all(self, request: HttpRequest) -> "HttpResponse":  # type: ignore
        self.model.discard_all()

    @view()
    def celery_purge(self, request: HttpRequest) -> "HttpResponse":  # type: ignore
        self.model.purge()

    @view()
    def celery_terminate(self, request: HttpRequest, pk: str) -> "HttpResponse":  # type: ignore
        obj: CeleryTaskModel = self.get_object(request, pk)
        obj.terminate()

    @view()
    def celery_inspect(self, request: HttpRequest, pk: int) -> HttpResponse:
        ctx = self.get_common_context(request, pk=pk)
        return render(
            request,
            [
                "admin/%s/%s/inspect.html" % (self.opts.app_label, self.opts.model_name),
                "admin/%s/inspect.html" % self.opts.app_label,
                "admin/celery_model/inspect.html",
            ],
            ctx,
        )

    # @view()
    # def celery_result(self, request: HttpRequest, pk: int) -> HttpResponse:
    #     self.get_common_context(request, pk=pk)
    #     result = TaskResult.objects.filter(task_id=self.object.curr_async_result_id).first()
    #     if result:
    #         url = reverse("admin:django_celery_results_taskresult_change", args=[result.pk])
    #         return redirect(url)
    #     else:
    #         self.message_user(request, "Result not found", messages.ERROR)

    @view()
    def celery_queue(self, request: "HttpRequest", pk: int) -> "HttpResponse":  # type: ignore
        obj: Optional[CeleryTaskModel]
        try:
            obj = self.get_object(request, str(pk))
            if obj.queue():
                self.message_user(request, f"Task scheduled: {obj.curr_async_result_id}")
        except Exception as e:
            self.message_user(request, f"{e.__class__.__name__}: {e}", messages.ERROR)

    @property
    def media(self) -> Media:
        response = super().media
        response._js_lists.append(["admin/celery.js"])
        return response
