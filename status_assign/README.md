This plugin assigns users according to groups on a project.

The plugin will assign users to a task when the task enters a specified
status, and vice-versa unassign those people from the task when the task
exits the status. In production we use it to assign supervisors to tasks
when the tasks status changes to "Supervisor Review". This means the
supervisor can stay within their "My Tasks" tab and get notified of the
tasks they need to review.

**Usage**

You will also need to setup project groups, to assign who needs to
assigned to what types of tasks. See the attached image.

- Setup a project group with the name of the status you want to track.
- Setup a subgroup within the above group with the name of the type of
task you want to track.
- Add the people you want to get assigned to a task, when the status
changes, to the subgroup.

[Walkthrough example](https://youtu.be/ZR53sGj1k_k)
