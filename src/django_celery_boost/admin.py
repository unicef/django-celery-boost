from typing import Any, Optional, Sequence

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin, confirm_action
from django.conf import settings
from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from django_celery_boost.models import CeleryTaskModel


class CeleryTaskModelAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    change_form_template = None
    terminate_template = None
    inspect_template = None
    queue_template = None

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

    def get_common_context(self, request: HttpRequest, pk: str = None, **kwargs: Any) -> dict[str, Any]:
        kwargs["flower_addr"] = getattr(settings, "CELERY_FLOW_ADDRESS", "")
        return super().get_common_context(request, pk, **kwargs)

    @button(
        label="Terminate", permission=lambda r, o, handler: handler.model_admin.has_queue_permission("terminate", r, o)
    )
    def celery_terminate(self, request: HttpRequest, pk: str) -> "HttpResponse":  # type: ignore
        obj: CeleryTaskModel = self.get_object(request, pk)
        ctx = self.get_common_context(request, pk, title=f"Confirm termination request for {obj}")

        def doit(request: "HttpRequest") -> HttpResponseRedirect:
            obj.terminate()
            redirect_url = reverse(
                "admin:%s_%s_change" % (obj._meta.app_label, obj._meta.model_name),
                args=(obj.pk,),
                current_app=self.admin_site.name,
            )
            return HttpResponseRedirect(redirect_url)

        return confirm_action(
            self,
            request,
            doit,
            "Do you really want to terminate this task?",
            "Terminated",
            extra_context=ctx,
            description="",
            template=self.terminate_template or [
                "%s/%s/%s/terminate.html" % (self.admin_site.name, self.opts.app_label, self.opts.model_name),
                "%s/%s/terminate.html" % (self.admin_site.name, self.opts.app_label),
                "%s/celery_boost/terminate.html" % self.admin_site.name,
            ],
        )

    @button(permission=lambda r, o, handler: handler.model_admin.has_queue_permission("inspect", r, o))
    def celery_inspect(self, request: HttpRequest, pk: str) -> HttpResponse:
        ctx = self.get_common_context(request, pk, title="Inspect Task")
        return render(
            request,
            self.inspect_template or [
                "%s/%s/%s/inspect.html" % (self.admin_site.name, self.opts.app_label, self.opts.model_name),
                "%s/%s/inspect.html" % (self.admin_site.name, self.opts.app_label),
                "%s/celery_boost/inspect.html" % self.admin_site.name,
            ],
            ctx,
        )

    def has_queue_permission(self, perm, request: HttpRequest, o: Optional[CeleryTaskModel]) -> bool:
        perm = "%s.%s_%s" % (self.model._meta.app_label, perm, self.model._meta.model_name)
        return request.user.has_perm(perm)

    @button(label="Queue", permission=lambda r, o, handler: handler.model_admin.has_queue_permission("queue", r, o))
    def celery_queue(self, request: "HttpRequest", pk: str) -> "HttpResponse":  # type: ignore
        obj: Optional[CeleryTaskModel]
        obj = self.get_object(request, pk)

        ctx = self.get_common_context(request, pk, title=f"Confirm queue action for {obj}")

        def doit(request: "HttpRequest") -> HttpResponseRedirect:
            obj.queue()
            redirect_url = reverse(
                "%s:%s_%s_change" % (self.admin_site.name, obj._meta.app_label, obj._meta.model_name),
                args=(obj.pk,),
                current_app=self.admin_site.name,
            )
            return HttpResponseRedirect(redirect_url)

        return confirm_action(
            self,
            request,
            doit,
            "Do you really want to queue this task?",
            "Queued",
            extra_context=ctx,
            description="",
            template=self.queue_template or [

                "%s/%s/%s/queue.html" % (self.admin_site.name, self.opts.app_label, self.opts.model_name),
                "%s/%s/queue.html" % (self.admin_site.name, self.opts.app_label),
                "%s/celery_boost/queue.html" % self.admin_site.name,
            ],
        )

    @button(label="Revoke", permission=lambda r, o, handler: handler.model_admin.has_queue_permission("revoke", r, o))
    def celery_revoke(self, request: "HttpRequest", pk: str) -> "HttpResponse":  # type: ignore
        obj: Optional[CeleryTaskModel]
        obj = self.get_object(request, pk)

        ctx = self.get_common_context(request, pk, title=f"Confirm revoking action for {obj}")

        def doit(request: "HttpRequest") -> HttpResponseRedirect:
            obj.revoke()
            redirect_url = reverse(
                "%s:%s_%s_change" % (self.admin_site.name, obj._meta.app_label, obj._meta.model_name),
                args=(obj.pk,),
                current_app=self.admin_site.name,
            )
            return HttpResponseRedirect(redirect_url)

        return confirm_action(
            self,
            request,
            doit,
            "Do you really want to queue this task?",
            "Revoked",
            extra_context=ctx,
            description="",
            template=[
                "%s/%s/%s/queue.html" % (self.admin_site.name, self.opts.app_label, self.opts.model_name),
                "%s/%s/queue.html" % (self.admin_site.name, self.opts.app_label),
                "%s/celery_boost/queue.html" % self.admin_site.name,
            ],
        )
