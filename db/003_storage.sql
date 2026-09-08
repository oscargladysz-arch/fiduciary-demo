-- Storage (decision 8.8): one private bucket, every object under the
-- workspace's id as the first folder, signed URLs with a short expiry for
-- downloads. Only the service role (the worker, the backup) writes objects.
-- Re-runnable.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('workspace', 'workspace', false, 52428800,
        array['application/json', 'text/csv', 'text/plain', 'text/markdown', 'application/pdf', 'application/gzip',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document'])
on conflict (id) do update set public = false, file_size_limit = 52428800,
  allowed_mime_types = excluded.allowed_mime_types;

-- a member reads under their workspace prefix. No insert, update or delete
-- policy for authenticated: uploads are the worker's, with the service role.
drop policy if exists workspace_member_read on storage.objects;
create policy workspace_member_read on storage.objects
  for select to authenticated
  using (
    bucket_id = 'workspace'
    and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

-- backups live under backups/ and are readable by nobody but the service role
