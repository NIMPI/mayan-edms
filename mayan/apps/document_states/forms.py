from __future__ import absolute_import, unicode_literals

import json

from django import forms
from django.forms.formsets import formset_factory
from django.utils.translation import ugettext_lazy as _

from common.forms import DynamicModelForm

from .classes import WorkflowAction
from .models import (
    Workflow, WorkflowState, WorkflowStateAction, WorkflowTransition
)
from .widgets import WorkflowImageWidget


class WorkflowActionSelectionForm(forms.Form):
    klass = forms.ChoiceField(choices=(), label=_('Action'))

    def __init__(self, *args, **kwargs):
        super(WorkflowActionSelectionForm, self).__init__(*args, **kwargs)

        self.fields['klass'].choices = [
            (
                key, klass.label
            ) for key, klass in WorkflowAction.get_all().items()
        ]


class WorkflowForm(forms.ModelForm):
    class Meta:
        fields = ('label', 'internal_name')
        model = Workflow


class WorkflowStateActionDynamicForm(DynamicModelForm):
    class Meta:
        fields = ('label', 'when', 'enabled', 'action_data')
        model = WorkflowStateAction
        widgets = {'action_data': forms.widgets.HiddenInput}

    def __init__(self, *args, **kwargs):
        result = super(
            WorkflowStateActionDynamicForm, self
        ).__init__(*args, **kwargs)
        if self.instance.action_data:
            for key, value in json.loads(self.instance.action_data).items():
                self.fields[key].initial = value

        return result

    def clean(self):
        data = super(WorkflowStateActionDynamicForm, self).clean()

        # Consolidate the dynamic fields into a single JSON field called
        # 'action_data'.
        action_data = {}

        for field in self.schema['fields']:
            action_data[field['name']] = data.pop(
                field['name'], field.get('default', None)
            )

        # Flatten the queryset to a list of ids
        action_data['tags'] = list(action_data['tags'].values_list('id', flat=True))
        data['action_data'] = json.dumps(action_data)
        return data


class WorkflowStateForm(forms.ModelForm):
    class Meta:
        fields = ('initial', 'label', 'completion')
        model = WorkflowState


class WorkflowTransitionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        workflow = kwargs.pop('workflow')
        super(WorkflowTransitionForm, self).__init__(*args, **kwargs)
        self.fields[
            'origin_state'
        ].queryset = self.fields[
            'origin_state'
        ].queryset.filter(workflow=workflow)

        self.fields[
            'destination_state'
        ].queryset = self.fields[
            'destination_state'
        ].queryset.filter(workflow=workflow)

    class Meta:
        fields = ('label', 'origin_state', 'destination_state')
        model = WorkflowTransition


class WorkflowTransitionTriggerEventRelationshipForm(forms.Form):
    label = forms.CharField(
        label=_('Label'), required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )
    relationship = forms.ChoiceField(
        label=_('Enabled'),
        widget=forms.RadioSelect(), choices=(
            ('no', _('No')),
            ('yes', _('Yes')),
        )
    )

    def __init__(self, *args, **kwargs):
        super(WorkflowTransitionTriggerEventRelationshipForm, self).__init__(
            *args, **kwargs
        )

        self.fields['label'].initial = self.initial['event_type'].label

        relationship = self.initial['transition'].trigger_events.filter(
            event_type=self.initial['event_type'],
        )

        if relationship.exists():
            self.fields['relationship'].initial = 'yes'
        else:
            self.fields['relationship'].initial = 'no'

    def save(self):
        relationship = self.initial['transition'].trigger_events.filter(
            event_type=self.initial['event_type'],
        )

        if self.cleaned_data['relationship'] == 'no':
            relationship.delete()
        elif self.cleaned_data['relationship'] == 'yes':
            if not relationship.exists():
                self.initial['transition'].trigger_events.create(
                    event_type=self.initial['event_type'],
                )


WorkflowTransitionTriggerEventRelationshipFormSet = formset_factory(
    WorkflowTransitionTriggerEventRelationshipForm, extra=0
)


class WorkflowInstanceTransitionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        workflow_instance = kwargs.pop('workflow_instance')
        super(WorkflowInstanceTransitionForm, self).__init__(*args, **kwargs)
        self.fields[
            'transition'
        ].queryset = workflow_instance.get_transition_choices(_user=user)

    transition = forms.ModelChoiceField(
        label=_('Transition'), queryset=WorkflowTransition.objects.none()
    )
    comment = forms.CharField(
        label=_('Comment'), required=False, widget=forms.widgets.Textarea()
    )


class WorkflowPreviewForm(forms.Form):
    preview = forms.CharField(widget=WorkflowImageWidget())

    def __init__(self, *args, **kwargs):
        instance = kwargs.pop('instance', None)
        super(WorkflowPreviewForm, self).__init__(*args, **kwargs)
        self.fields['preview'].initial = instance
